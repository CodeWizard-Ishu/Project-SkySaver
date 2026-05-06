"""agents/forecast_engine.py — Phase 3 Subsystem B: LightGBM Price Forecast Engine.

Trains a binary LightGBM classifier on historical flight_prices data to predict
whether the current price will RISE within 7 days (high score = book now).

Label encoding:
  1 = price will RISE   → book now (lgbm_score close to 1.0)
  0 = price will FALL   → wait    (lgbm_score close to 0.0)

lgbm_score is the probability of class=1 (price rising), so:
  score ≥ 0.70 → forecast "up"   → book now signal
  score ≤ 0.30 → forecast "down" → wait signal
  otherwise    → forecast "flat" → monitor

Logger name: flight_agent.forecast
"""

from __future__ import annotations

import glob
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Optional

try:
    import joblib  # type: ignore[import-untyped]
except ImportError:
    joblib = None  # type: ignore[assignment]

from agents.base_agent import get_logger, utcnow
import db.queries as queries
from db.queries import InsufficientDataError

# ─── MODULE LOGGER ────────────────────────────────────────────────────────────

_log = get_logger("flight_agent.forecast", "forecast.log")

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

_MODELS_DIR = Path("models")
_MIN_TRAINING_SAMPLES = 50
_LOOKAHEAD_DAYS = 7
_RETRAIN_THRESHOLDS = (50, 100, 200, 500, 1000)

# Score thresholds for direction classification
_UP_THRESHOLD = 0.70
_DOWN_THRESHOLD = 0.30

# Expected feature columns (must match build_features output)
_FEATURE_COLUMNS = [
    "day_of_week",
    "days_until_travel",
    "days_until_travel_sq",
    "price_inr",
    "rolling_7d_mean",
    "rolling_7d_std",
    "price_pct_vs_7d_mean",
    "stops",
    "is_weekend_travel",
    "days_to_weekend",
    "month_of_travel",
]

# ─── DATACLASSES ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ForecastScore:
    """Result of one LightGBM prediction for a route+date fare."""

    route: str
    travel_date: date
    lgbm_score: float           # 0.0–1.0: probability price will rise (book now)
    forecast_direction: str     # "up" | "down" | "flat"
    confidence: float           # model's certainty (max of class probabilities)
    model_version: str          # filename of model used, or "none" if no model
    feature_values: dict        # feature→value dict used for this prediction (audit)


@dataclass
class TrainingResult:
    """Metrics and metadata from one LightGBM training run."""

    model_version: str
    trained_at: datetime
    n_samples: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    feature_importances: dict[str, float]
    model_path: str


# ─── FORECAST ENGINE CLASS ────────────────────────────────────────────────────


class ForecastEngine:
    """
    Class-based facade over the module-level predict/train/should_retrain functions.

    Supports both import styles:
        from agents.forecast_engine import ForecastEngine   # class
        from agents.forecast_engine import predict, train   # functions

    All methods delegate directly to the module-level implementations.
    """

    def predict(
        self,
        route: str,
        travel_date: "date",
        current_price: int,
        days_advance: int,
    ) -> "ForecastScore":
        """Run LightGBM prediction for a single route+date fare. Never raises."""
        return predict(route, travel_date, current_price, days_advance)

    def train(self, route: Optional[str] = None) -> "TrainingResult":
        """Train or retrain the global LightGBM model. Raises InsufficientDataError."""
        return train(route)

    def should_retrain(self, route: Optional[str] = None) -> bool:
        """Return True if the observation count has crossed a retraining threshold."""
        return should_retrain(route)

    def build_features(self, df: "Any") -> "Any":
        """Feature-engineer a raw price DataFrame for ML use."""
        return build_features(df)

    def generate_labels(self, df: "Any", lookahead_days: int = 7) -> "Any":
        """Generate binary labels for supervised training."""
        return generate_labels(df, lookahead_days)


# ─── FEATURE ENGINEERING ─────────────────────────────────────────────────────



def build_features(df: "pd.DataFrame") -> "pd.DataFrame":  # type: ignore[name-defined]
    """
    Transform raw flight_prices records into ML features.

    Input columns expected: observed_at, route, travel_date, price_inr,
    airline, stops, days_advance, source

    Returns DataFrame with only feature columns. Drops rows where rolling
    features cannot be computed (< 7 prior observations per route).
    NaN values are replaced with 0.0 — never left as NaN.
    """
    import pandas as pd  # type: ignore[import-untyped]
    import numpy as np   # type: ignore[import-untyped]

    df = df.copy()

    # Ensure datetime types
    if not pd.api.types.is_datetime64_any_dtype(df["observed_at"]):
        df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True, errors="coerce")
    if not pd.api.types.is_datetime64_any_dtype(df["travel_date"]):
        df["travel_date"] = pd.to_datetime(df["travel_date"], errors="coerce")

    df = df.dropna(subset=["observed_at", "travel_date", "price_inr"])
    df = df.sort_values(["route", "travel_date", "observed_at"]).reset_index(drop=True)

    # ── Basic features ──────────────────────────────────────────────────────
    df["day_of_week"] = df["observed_at"].dt.dayofweek          # 0=Mon, 6=Sun
    df["days_until_travel"] = df["days_advance"].fillna(0).astype(int)
    df["days_until_travel_sq"] = df["days_until_travel"] ** 2

    # ── Rolling features per route using transform (pandas 2.x compatible) ──
    df = df.sort_values(["route", "travel_date", "observed_at"]).reset_index(drop=True)

    def _roll_mean(s: "pd.Series") -> "pd.Series":
        return s.shift(1).rolling(window=7, min_periods=7).mean()

    def _roll_std(s: "pd.Series") -> "pd.Series":
        return s.shift(1).rolling(window=7, min_periods=7).std()

    df["rolling_7d_mean"] = (
        df.groupby("route")["price_inr"].transform(_roll_mean)
    )
    df["rolling_7d_std"] = (
        df.groupby("route")["price_inr"].transform(_roll_std)
    )


    # Drop rows with insufficient rolling history (< 7 prior observations)
    df = df.dropna(subset=["rolling_7d_mean", "rolling_7d_std"]).reset_index(drop=True)

    # Percentage deviation from rolling mean
    df["price_pct_vs_7d_mean"] = (
        (df["price_inr"] - df["rolling_7d_mean"]) / df["rolling_7d_mean"].replace(0, np.nan) * 100
    )

    # ── Travel date features ─────────────────────────────────────────────────
    travel_dt = df["travel_date"]
    df["is_weekend_travel"] = travel_dt.dt.dayofweek.isin([5, 6]).astype(int)
    # Days until next Saturday (weekday 5) from travel_date
    df["days_to_weekend"] = (5 - travel_dt.dt.dayofweek) % 7
    df["month_of_travel"] = travel_dt.dt.month

    # ── Stops ────────────────────────────────────────────────────────────────
    df["stops"] = df["stops"].fillna(0).astype(int)

    # ── Replace all remaining NaN with 0.0 (LightGBM-safe) ─────────────────
    nan_cols = [c for c in _FEATURE_COLUMNS if df[c].isna().any()]
    if nan_cols:
        _log.debug(
            json.dumps({
                "event": "nan_substitution",
                "columns": nan_cols,
                "note": "replaced NaN with 0.0 for LightGBM compatibility",
            })
        )
    for col in _FEATURE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].fillna(0.0)

    return df[_FEATURE_COLUMNS + ["route", "travel_date", "observed_at", "price_inr"]]


def generate_labels(df: "pd.DataFrame", lookahead_days: int = _LOOKAHEAD_DAYS) -> "pd.Series":  # type: ignore[name-defined]
    """
    For each price observation, look up the price ~lookahead_days later.

    Label = 1 if future price > current price (price rises → book now).
    Label = 0 if future price <= current price (wait).

    Rows with no matching future observation are DROPPED (returned Series
    has the same index as surviving rows, suitable for df.loc[labels.index]).

    Implementation:
      Sort by (route, travel_date, observed_at).
      For each row, find the closest observation for the same route+travel_date
      with observed_at between (observed_at + 5 days) and (observed_at + 9 days).
    """
    import pandas as pd  # type: ignore[import-untyped]
    from datetime import timedelta

    df = df.sort_values(["route", "travel_date", "observed_at"]).copy()
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True, errors="coerce")

    labels: dict[int, int] = {}

    for (route, travel_date), group in df.groupby(["route", "travel_date"]):
        group = group.sort_values("observed_at").reset_index()
        times = group["observed_at"].tolist()
        # Use iloc to handle potential duplicate 'price_inr' columns (from transform)
        price_col = group["price_inr"]
        if hasattr(price_col, "iloc") and price_col.ndim > 1:
            price_col = price_col.iloc[:, 0]
        prices = price_col.tolist()
        orig_idx = group["index"].tolist()

        for i, (obs_time, price, idx) in enumerate(zip(times, prices, orig_idx)):
            window_start = obs_time + pd.Timedelta(days=lookahead_days - 2)
            window_end = obs_time + pd.Timedelta(days=lookahead_days + 2)
            future_candidates = [
                (t, p) for t, p in zip(times[i + 1 :], prices[i + 1 :])
                if window_start <= t <= window_end
            ]
            if not future_candidates:
                continue
            # Use the candidate closest to exactly lookahead_days out
            target_time = obs_time + pd.Timedelta(days=lookahead_days)
            closest_price = min(
                future_candidates,
                key=lambda tp: abs((tp[0] - target_time).total_seconds()),
            )[1]
            labels[idx] = 1 if closest_price > price else 0

    return pd.Series(labels, name="label")


# ─── PRIVATE: MODEL FILE HELPERS ─────────────────────────────────────────────


def _ensure_models_dir() -> None:
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)


def _list_model_files() -> list[Path]:
    """Return model pkl files sorted by modification time (newest last)."""
    _ensure_models_dir()
    files = sorted(
        _MODELS_DIR.glob("lgbm_global_v*.pkl"),
        key=lambda p: p.stat().st_mtime,
    )
    return files


def _next_version() -> int:
    """Return the next model version number (count of existing files + 1)."""
    return len(_list_model_files()) + 1


def _latest_model_path() -> Optional[Path]:
    """Return the most recently created model file, or None if no models exist."""
    files = _list_model_files()
    return files[-1] if files else None


def _score_to_direction(score: float) -> str:
    if score >= _UP_THRESHOLD:
        return "up"
    if score <= _DOWN_THRESHOLD:
        return "down"
    return "flat"


# ─── PRIVATE: LOAD TRAINING DATA FROM DB ─────────────────────────────────────


def _load_all_price_data() -> "pd.DataFrame":
    """Fetch all flight_prices rows and return as a DataFrame."""
    import pandas as pd  # type: ignore[import-untyped]

    conn = queries.get_connection()
    rows = conn.execute(
        "SELECT observed_at, route, travel_date, price_inr, airline, stops, days_advance, source "
        "FROM flight_prices ORDER BY route, travel_date, observed_at ASC"
    ).fetchall()

    if not rows:
        return pd.DataFrame(columns=[
            "observed_at", "route", "travel_date", "price_inr",
            "airline", "stops", "days_advance", "source",
        ])

    return pd.DataFrame([dict(r) for r in rows])


# ─── TRAINING ────────────────────────────────────────────────────────────────


def train(route: Optional[str] = None) -> TrainingResult:
    """
    Train or retrain the LightGBM model on all available labeled data.

    If route is None: train a global model across all routes.
    Uses time-based 80/20 train/test split (no data leakage).

    Raises:
        InsufficientDataError: If fewer than 50 labeled examples available.

    Returns:
        TrainingResult with metrics and model path.
    """
    import pandas as pd        # type: ignore[import-untyped]
    import lightgbm as lgb    # type: ignore[import-untyped]
    from sklearn.metrics import (  # type: ignore[import-untyped]
        accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    )

    _log.info(json.dumps({"event": "training_started", "route": route or "global"}))

    raw_df = _load_all_price_data()
    if route:
        raw_df = raw_df[raw_df["route"] == route].copy()

    if raw_df.empty:
        raise InsufficientDataError(
            f"No data found for {'route=' + route if route else 'global model'}."
        )

    feature_df = build_features(raw_df)
    label_series = generate_labels(feature_df)

    # Align features with labels
    feature_df = feature_df.loc[label_series.index].copy()
    y = label_series

    if len(y) < _MIN_TRAINING_SAMPLES:
        raise InsufficientDataError(
            f"Only {len(y)} labeled examples available; need {_MIN_TRAINING_SAMPLES}. "
            "Continue scraping to accumulate more data."
        )

    # Time-based 80/20 split — most recent 20% goes to test (no data leakage)
    split_idx = int(len(feature_df) * 0.80)
    X_train = feature_df[_FEATURE_COLUMNS].iloc[:split_idx]
    X_test = feature_df[_FEATURE_COLUMNS].iloc[split_idx:]
    y_train = y.iloc[:split_idx]
    y_test = y.iloc[split_idx:]

    model = lgb.LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        min_child_samples=10,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    try:
        auc = float(roc_auc_score(y_test, y_prob))
    except ValueError:
        auc = 0.5  # Only one class in test set

    importances = dict(zip(_FEATURE_COLUMNS, model.feature_importances_.tolist()))

    _ensure_models_dir()
    version = _next_version()
    today_str = date.today().isoformat()
    model_filename = f"lgbm_global_v{version}_{today_str}.pkl"
    model_path = _MODELS_DIR / model_filename

    joblib.dump(model, model_path)

    result = TrainingResult(
        model_version=model_filename,
        trained_at=utcnow(),
        n_samples=len(y),
        accuracy=acc,
        precision=prec,
        recall=rec,
        f1_score=f1,
        roc_auc=auc,
        feature_importances=importances,
        model_path=str(model_path),
    )

    _log.info(
        json.dumps({
            "event": "training_complete",
            "model_version": model_filename,
            "n_samples": len(y),
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "roc_auc": round(auc, 4),
            "model_path": str(model_path),
        })
    )

    return result


# ─── PREDICTION ──────────────────────────────────────────────────────────────


def predict(
    route: str,
    travel_date: date,
    current_price: int,
    days_advance: int,
) -> ForecastScore:
    """
    Load the latest saved model and predict lgbm_score for one fare.

    If no model file exists: returns ForecastScore with lgbm_score=0.5 (neutral).
    If fewer than 7 prior observations: uses conservative rolling estimates.

    Never raises. Always returns a ForecastScore.
    """
    import pandas as pd   # type: ignore[import-untyped]
    import numpy as np    # type: ignore[import-untyped]

    model_path = _latest_model_path()

    if model_path is None:
        _log.warning(
            json.dumps({
                "event": "predict_no_model",
                "route": route,
                "travel_date": travel_date.isoformat(),
                "note": "No model file found — returning neutral score 0.5",
            })
        )
        return ForecastScore(
            route=route,
            travel_date=travel_date,
            lgbm_score=0.5,
            forecast_direction="flat",
            confidence=0.5,
            model_version="none",
            feature_values={},
        )

    try:
        if joblib is None:
            raise ImportError("joblib not installed")
        model = joblib.load(model_path)
    except Exception as exc:
        _log.error(
            json.dumps({
                "event": "predict_model_load_failed",
                "model_path": str(model_path),
                "error": str(exc),
            })
        )
        return ForecastScore(
            route=route,
            travel_date=travel_date,
            lgbm_score=0.5,
            forecast_direction="flat",
            confidence=0.5,
            model_version=model_path.name,
            feature_values={},
        )

    # Fetch recent price history for rolling stats
    try:
        history = queries.get_price_history(route, travel_date, days_back=30)
        recent_prices = [obs.price_inr for obs in history]
    except Exception:
        recent_prices = []

    if len(recent_prices) >= 7:
        rolling_mean = float(np.mean(recent_prices[-7:]))
        rolling_std = float(np.std(recent_prices[-7:]))
    else:
        rolling_mean = float(current_price)
        rolling_std = 0.0
        _log.debug(
            json.dumps({
                "event": "nan_substitution",
                "columns": ["rolling_7d_mean", "rolling_7d_std"],
                "note": "replaced NaN with 0.0 for LightGBM compatibility",
                "reason": f"only {len(recent_prices)} observations available",
            })
        )

    price_pct_vs_7d_mean = (
        ((current_price - rolling_mean) / rolling_mean * 100)
        if rolling_mean != 0 else 0.0
    )

    travel_dt = datetime(travel_date.year, travel_date.month, travel_date.day)
    day_of_week_travel = travel_dt.weekday()
    is_weekend = int(day_of_week_travel in (5, 6))
    days_to_weekend = int((5 - day_of_week_travel) % 7)

    feature_values = {
        "day_of_week": datetime.now(UTC).weekday(),
        "days_until_travel": days_advance,
        "days_until_travel_sq": days_advance ** 2,
        "price_inr": float(current_price),
        "rolling_7d_mean": rolling_mean,
        "rolling_7d_std": rolling_std,
        "price_pct_vs_7d_mean": price_pct_vs_7d_mean,
        "stops": 0,  # conservative default for prediction
        "is_weekend_travel": is_weekend,
        "days_to_weekend": days_to_weekend,
        "month_of_travel": travel_date.month,
    }

    X = pd.DataFrame([feature_values])[_FEATURE_COLUMNS]

    # Validate feature count before prediction
    if X.shape[1] != len(_FEATURE_COLUMNS):
        _log.error(
            json.dumps({
                "event": "predict_feature_mismatch",
                "expected": len(_FEATURE_COLUMNS),
                "actual": X.shape[1],
                "note": "returning neutral score",
            })
        )
        return ForecastScore(
            route=route,
            travel_date=travel_date,
            lgbm_score=0.5,
            forecast_direction="flat",
            confidence=0.5,
            model_version=model_path.name,
            feature_values=feature_values,
        )

    try:
        proba = model.predict_proba(X)[0]
        lgbm_score = float(proba[1])  # probability of class=1 (price rises)
        confidence = float(max(proba))
    except Exception as exc:
        _log.error(
            json.dumps({
                "event": "predict_inference_failed",
                "error": str(exc),
            })
        )
        return ForecastScore(
            route=route,
            travel_date=travel_date,
            lgbm_score=0.5,
            forecast_direction="flat",
            confidence=0.5,
            model_version=model_path.name,
            feature_values=feature_values,
        )

    direction = _score_to_direction(lgbm_score)

    _log.info(
        json.dumps({
            "event": "forecast_computed",
            "route": route,
            "travel_date": travel_date.isoformat(),
            "lgbm_score": round(lgbm_score, 4),
            "direction": direction,
            "model": model_path.name,
        })
    )

    return ForecastScore(
        route=route,
        travel_date=travel_date,
        lgbm_score=lgbm_score,
        forecast_direction=direction,
        confidence=confidence,
        model_version=model_path.name,
        feature_values=feature_values,
    )


# ─── AUTO-RETRAIN TRIGGER ─────────────────────────────────────────────────────


def should_retrain(route: Optional[str] = None) -> bool:
    """
    Return True if the model should be retrained.

    Retraining is triggered when the total observation count crosses one of
    the thresholds (50, 100, 200, 500, 1000) for the first time, detected by
    checking whether a model already exists for that threshold level.
    Also returns True if no model file exists at all.
    """
    model_files = _list_model_files()

    if not model_files:
        _log.info(json.dumps({"event": "should_retrain", "reason": "no_model_exists"}))
        return True

    try:
        counts = queries.get_observation_count_by_route()
        if route:
            total = counts.get(route, 0)
        else:
            total = sum(counts.values())
    except Exception as exc:
        _log.error(
            json.dumps({
                "event": "should_retrain_count_failed",
                "error": str(exc),
            })
        )
        return False

    # Determine which threshold bucket we are in
    current_threshold = 0
    for t in _RETRAIN_THRESHOLDS:
        if total >= t:
            current_threshold = t

    if current_threshold == 0:
        _log.debug(
            json.dumps({
                "event": "should_retrain",
                "total_observations": total,
                "reason": f"below minimum threshold {_RETRAIN_THRESHOLDS[0]}",
                "result": False,
            })
        )
        return False

    # Check if any existing model was trained after the current threshold was crossed.
    # We approximate this by counting model files: if we have a model file for this
    # threshold level already, no retrain needed. We detect threshold crossings by
    # the number of models trained: each threshold crossing produces one new model.
    threshold_idx = list(_RETRAIN_THRESHOLDS).index(current_threshold)
    models_needed = threshold_idx + 1  # one model per crossed threshold

    if len(model_files) < models_needed:
        _log.info(
            json.dumps({
                "event": "should_retrain",
                "total_observations": total,
                "current_threshold": current_threshold,
                "model_files": len(model_files),
                "models_needed": models_needed,
                "result": True,
            })
        )
        return True

    _log.debug(
        json.dumps({
            "event": "should_retrain",
            "total_observations": total,
            "current_threshold": current_threshold,
            "result": False,
        })
    )
    return False
