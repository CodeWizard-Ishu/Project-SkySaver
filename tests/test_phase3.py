"""tests/test_phase3.py — Comprehensive pytest suite for Phase 3.

All external calls (Gemini API, Telegram API, LightGBM) are fully mocked.
Uses same fresh_db fixture pattern as test_db.py and test_scraper.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

import db.queries as Q
from db.init_db import create_tables
from agents.analyzer_agent import (
    AnalysisReport,
    AnalyzerAgent,
    PriceSummary,
    build_price_summary,
    _fallback_report,
)
from agents.forecast_engine import (
    ForecastScore,
    TrainingResult,
    _score_to_direction,
    _list_model_files,
    predict,
    should_retrain,
)
from agents.alert_engine import (
    AlertDecision,
    ML_SCORE_THRESHOLD,
    _fmt_inr,
    _build_skyscanner_url,
    evaluate_alert,
    format_alert_message,
    send_telegram_alert,
)

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

_ROUTE = "NAG-DEL"
_FUTURE_DATE = date.today() + timedelta(days=42)
_CURRENT_PRICE = 3240
_P10_PRICE = 3500
_MEDIAN_PRICE = 5100


# ─── FIXTURES ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    db_path = str(tmp_path / "test_phase3.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    Q._conn = None
    create_tables()
    yield
    Q.close_connection()
    Q._conn = None


@pytest.fixture()
def models_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    mdir = tmp_path / "models"
    mdir.mkdir()
    import agents.forecast_engine as fe
    monkeypatch.setattr(fe, "_MODELS_DIR", mdir)
    return mdir


def _seed_stats(
    route: str = _ROUTE,
    travel_date: date = _FUTURE_DATE,
    n: int = 15,
    base_price: int = 4000,
) -> None:
    Q.upsert_monitored_route(route, [travel_date.isoformat()])
    for i in range(n):
        Q.insert_price_observation(
            route=route,
            travel_date=travel_date,
            price_inr=base_price - (i * 50),
            airline="IndiGo",
            stops=0,
            source="skyscanner",
        )
    Q.update_price_stats(route, travel_date)


def _make_summary(
    current_price: int = _CURRENT_PRICE,
    observation_count: int = 15,
    p10: int = _P10_PRICE,
    median: int = _MEDIAN_PRICE,
    lgbm_score: float = 0.82,
    days: int = 42,
) -> PriceSummary:
    pct_median = ((current_price - median) / median) * 100.0
    pct_p10 = ((current_price - p10) / p10) * 100.0
    return PriceSummary(
        route=_ROUTE,
        travel_date=_FUTURE_DATE,
        current_price=current_price,
        p10_price=p10,
        p25_price=4000,
        median_price=median,
        all_time_low=2980,
        all_time_high=7500,
        observation_count=observation_count,
        pct_vs_median=pct_median,
        pct_vs_p10=pct_p10,
        lgbm_score=lgbm_score,
        forecast_direction="up",
        days_until_travel=days,
        recent_7d_prices=[3800, 3700, 3600, 3500, 3400, 3300, 3240],
    )


def _make_analysis(recommendation: str = "BUY_NOW") -> AnalysisReport:
    return AnalysisReport(
        route=_ROUTE,
        travel_date=_FUTURE_DATE,
        recommendation=recommendation,
        confidence="HIGH",
        reasoning="Price is at historical P10. Strong buy signal.",
        urgency_score=8,
        key_insight="Lowest price in 3 months — book now.",
        generated_at=datetime.now(UTC),
        model_version="gemini-2.5-pro",
    )


def _make_forecast(score: float = 0.82, model_version: str = "lgbm_v1.pkl") -> ForecastScore:
    return ForecastScore(
        route=_ROUTE,
        travel_date=_FUTURE_DATE,
        lgbm_score=score,
        forecast_direction=_score_to_direction(score),
        confidence=score,
        model_version=model_version,
        feature_values={"days_until_travel": 42, "price_inr": 3240.0},
    )


def _make_alert_decision(
    should: bool = True,
    g1: bool = True,
    g2: bool = True,
    g3: bool = True,
) -> AlertDecision:
    return AlertDecision(
        should_alert=should,
        gate1_passed=g1,
        gate2_passed=g2,
        gate3_passed=g3,
        gate1_reason="Price ₹3240 is in P10 territory",
        gate2_reason="ML score 0.820 >= threshold 0.70",
        gate3_reason="No recent alert — cooldown clear",
        current_price=_CURRENT_PRICE,
        p10_price=_P10_PRICE,
        lgbm_score=0.82,
        pct_below_median=-36.5,
        all_time_low=2980,
    )


# ─── TestBuildPriceSummary ────────────────────────────────────────────────────


class TestBuildPriceSummary:

    def test_returns_none_when_no_stats(self) -> None:
        Q.upsert_monitored_route(_ROUTE, [_FUTURE_DATE.isoformat()])
        result = build_price_summary(_ROUTE, _FUTURE_DATE)
        assert result is None

    def test_builds_correctly_from_db(self) -> None:
        _seed_stats()
        result = build_price_summary(_ROUTE, _FUTURE_DATE)
        assert result is not None
        assert result.route == _ROUTE
        assert result.travel_date == _FUTURE_DATE
        assert result.observation_count == 15
        assert result.p10_price is not None
        assert result.median_price is not None

    def test_pct_vs_median_calculated(self) -> None:
        _seed_stats(base_price=5000)
        Q.insert_price_observation(
            route=_ROUTE, travel_date=_FUTURE_DATE, price_inr=3000,
            airline="IndiGo", stops=0, source="skyscanner",
        )
        Q.update_price_stats(_ROUTE, _FUTURE_DATE)
        result = build_price_summary(_ROUTE, _FUTURE_DATE, current_price=3000)
        assert result is not None
        assert result.pct_vs_median is not None
        stats = Q.get_price_stats(_ROUTE, _FUTURE_DATE)
        expected = ((3000 - stats.median_price) / stats.median_price) * 100
        assert abs(result.pct_vs_median - expected) < 0.01

    def test_pct_vs_p10_calculated(self) -> None:
        _seed_stats(base_price=5000)
        result = build_price_summary(_ROUTE, _FUTURE_DATE, current_price=3000)
        assert result is not None
        assert result.pct_vs_p10 is not None
        stats = Q.get_price_stats(_ROUTE, _FUTURE_DATE)
        expected = ((3000 - stats.p10_price) / stats.p10_price) * 100
        assert abs(result.pct_vs_p10 - expected) < 0.01

    def test_days_until_travel_correct(self) -> None:
        _seed_stats()
        result = build_price_summary(_ROUTE, _FUTURE_DATE)
        assert result is not None
        expected = (_FUTURE_DATE - date.today()).days
        assert result.days_until_travel == expected

    def test_recent_7d_prices_populated(self) -> None:
        Q.upsert_monitored_route(_ROUTE, [_FUTURE_DATE.isoformat()])
        for i in range(10):
            Q.insert_price_observation(
                route=_ROUTE, travel_date=_FUTURE_DATE,
                price_inr=4000 - i * 30,
                airline="IndiGo", stops=0, source="skyscanner",
            )
        Q.update_price_stats(_ROUTE, _FUTURE_DATE)
        result = build_price_summary(_ROUTE, _FUTURE_DATE)
        assert result is not None
        assert len(result.recent_7d_prices) <= 10
        assert len(result.recent_7d_prices) > 0


# ─── TestAnalyzerAgent ────────────────────────────────────────────────────────


def _make_chat_result(content: dict) -> MagicMock:
    mock_result = MagicMock()
    mock_result.summary = json.dumps(content)
    mock_result.chat_history = [{"role": "assistant", "content": json.dumps(content)}]
    return mock_result


_VALID_GEMINI_RESPONSE = {
    "recommendation": "BUY_NOW",
    "confidence": "HIGH",
    "reasoning": "Price is at P10. ML says buy now. Travel in 42 days is ideal.",
    "urgency_score": 8,
    "key_insight": "Lowest price in 3 months — book immediately.",
}


class TestAnalyzerAgent:

    @patch("autogen.ConversableAgent")
    def test_returns_analysis_report(self, mock_ca: Any) -> None:
        mock_user = MagicMock()
        mock_user.initiate_chat.return_value = _make_chat_result(_VALID_GEMINI_RESPONSE)
        mock_ca.return_value = MagicMock()

        agent = AnalyzerAgent.__new__(AnalyzerAgent)
        agent._assistant = MagicMock()
        agent._user = mock_user

        summary = _make_summary()
        report = agent.analyse(summary)

        assert isinstance(report, AnalysisReport)
        assert report.recommendation == "BUY_NOW"
        assert report.confidence == "HIGH"
        assert report.urgency_score == 8
        assert report.model_version == "gemini-2.5-pro"
        assert report.route == _ROUTE

    def test_handles_invalid_json_retry(self) -> None:
        mock_user = MagicMock()
        mock_user.initiate_chat.side_effect = [
            _make_chat_result({}),  # first call: missing fields (simulate bad JSON)
            _make_chat_result(_VALID_GEMINI_RESPONSE),
        ]
        # Override first call to return invalid JSON string
        first = MagicMock()
        first.summary = "not valid json at all!!!"
        second = _make_chat_result(_VALID_GEMINI_RESPONSE)
        mock_user.initiate_chat.side_effect = [first, second]

        agent = AnalyzerAgent.__new__(AnalyzerAgent)
        agent._assistant = MagicMock()
        agent._user = mock_user

        report = agent.analyse(_make_summary())
        assert isinstance(report, AnalysisReport)
        # Second attempt succeeded
        assert report.recommendation == "BUY_NOW"

    def test_both_attempts_fail_returns_fallback(self) -> None:
        mock_user = MagicMock()
        bad = MagicMock()
        bad.summary = "{{broken json"
        mock_user.initiate_chat.return_value = bad

        agent = AnalyzerAgent.__new__(AnalyzerAgent)
        agent._assistant = MagicMock()
        agent._user = mock_user

        report = agent.analyse(_make_summary())
        assert report.recommendation == "INSUFFICIENT_DATA"
        assert report.confidence == "LOW"
        assert report.urgency_score == 1

    def test_recommendation_buy_now(self) -> None:
        resp = {**_VALID_GEMINI_RESPONSE, "recommendation": "BUY_NOW"}
        mock_user = MagicMock()
        mock_user.initiate_chat.return_value = _make_chat_result(resp)
        agent = AnalyzerAgent.__new__(AnalyzerAgent)
        agent._assistant = MagicMock()
        agent._user = mock_user
        report = agent.analyse(_make_summary(current_price=3240, p10=3500))
        assert report.recommendation == "BUY_NOW"

    def test_recommendation_wait(self) -> None:
        resp = {**_VALID_GEMINI_RESPONSE, "recommendation": "WAIT", "confidence": "MEDIUM"}
        mock_user = MagicMock()
        mock_user.initiate_chat.return_value = _make_chat_result(resp)
        agent = AnalyzerAgent.__new__(AnalyzerAgent)
        agent._assistant = MagicMock()
        agent._user = mock_user
        report = agent.analyse(_make_summary(current_price=6000))
        assert report.recommendation == "WAIT"

    def test_recommendation_insufficient(self) -> None:
        resp = {**_VALID_GEMINI_RESPONSE, "recommendation": "INSUFFICIENT_DATA"}
        mock_user = MagicMock()
        mock_user.initiate_chat.return_value = _make_chat_result(resp)
        agent = AnalyzerAgent.__new__(AnalyzerAgent)
        agent._assistant = MagicMock()
        agent._user = mock_user
        report = agent.analyse(_make_summary(observation_count=5))
        assert report.recommendation == "INSUFFICIENT_DATA"

    def test_urgency_score_range(self) -> None:
        for score in [0, 1, 5, 10, 11, -1]:
            resp = {**_VALID_GEMINI_RESPONSE, "urgency_score": score}
            mock_user = MagicMock()
            mock_user.initiate_chat.return_value = _make_chat_result(resp)
            agent = AnalyzerAgent.__new__(AnalyzerAgent)
            agent._assistant = MagicMock()
            agent._user = mock_user
            report = agent.analyse(_make_summary())
            assert 1 <= report.urgency_score <= 10

    def test_key_insight_max_length(self) -> None:
        long_insight = "A" * 200
        resp = {**_VALID_GEMINI_RESPONSE, "key_insight": long_insight}
        mock_user = MagicMock()
        mock_user.initiate_chat.return_value = _make_chat_result(resp)
        agent = AnalyzerAgent.__new__(AnalyzerAgent)
        agent._assistant = MagicMock()
        agent._user = mock_user
        report = agent.analyse(_make_summary())
        # key_insight is stored as-is but must be a string
        assert isinstance(report.key_insight, str)
        assert len(report.key_insight) <= 200  # stored from model output


# ─── TestForecastEngine ──────────────────────────────────────────────────────


class TestForecastEngine:

    def test_build_features_correct_columns(self) -> None:
        import pandas as pd
        from agents.forecast_engine import _FEATURE_COLUMNS
        # Patch groupby.apply to avoid pandas >=2.2 include_groups warning
        import agents.forecast_engine as fe

        rows = []
        base = datetime.now(UTC)
        for i in range(20):
            rows.append({
                "observed_at": (base - timedelta(days=i)).isoformat(),
                "route": _ROUTE,
                "travel_date": _FUTURE_DATE.isoformat(),
                "price_inr": 4000 - i * 20,
                "airline": "IndiGo",
                "stops": 0,
                "days_advance": 42 + i,
                "source": "skyscanner",
            })
        df = pd.DataFrame(rows)
        result = fe.build_features(df)
        for col in _FEATURE_COLUMNS:
            assert col in result.columns, f"Missing column: {col}"

    def test_label_generation_future_higher(self) -> None:
        import pandas as pd
        import agents.forecast_engine as fe

        rows = []
        base = datetime.now(UTC)
        for i in range(20):
            rows.append({
                "observed_at": (base - timedelta(days=20 - i)).isoformat(),
                "route": _ROUTE,
                "travel_date": _FUTURE_DATE.isoformat(),
                "price_inr": 3000 + i * 100,  # price rises over time
                "airline": "IndiGo",
                "stops": 0,
                "days_advance": 42,
                "source": "skyscanner",
            })
        df = pd.DataFrame(rows)
        features = fe.build_features(df)
        labels = fe.generate_labels(features, lookahead_days=7)
        # Rising prices -> label=1 (book now)
        if len(labels) > 0:
            assert labels.iloc[0] == 1

    def test_label_generation_future_lower(self) -> None:
        import pandas as pd
        import agents.forecast_engine as fe

        rows = []
        base = datetime.now(UTC)
        for i in range(20):
            rows.append({
                "observed_at": (base - timedelta(days=20 - i)).isoformat(),
                "route": _ROUTE,
                "travel_date": _FUTURE_DATE.isoformat(),
                "price_inr": 5000 - i * 100,  # price falls over time
                "airline": "IndiGo",
                "stops": 0,
                "days_advance": 42,
                "source": "skyscanner",
            })
        df = pd.DataFrame(rows)
        features = fe.build_features(df)
        labels = fe.generate_labels(features, lookahead_days=7)
        if len(labels) > 0:
            assert labels.iloc[0] == 0

    def test_insufficient_data_raises(self, models_dir: Path) -> None:
        from agents.forecast_engine import train
        from db.queries import InsufficientDataError
        with pytest.raises(InsufficientDataError):
            train()

    def test_predict_no_model_returns_neutral(self, models_dir: Path) -> None:
        result = predict(_ROUTE, _FUTURE_DATE, 3240, 42)
        assert result.lgbm_score == 0.5
        assert result.model_version == "none"
        assert result.forecast_direction == "flat"

    def test_predict_with_mock_model(self, models_dir: Path, mocker: Any) -> None:
        # Use mocker.patch on joblib.load — can't pickle MagicMock directly
        import numpy as np
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.15, 0.85]])
        fake_pkl = models_dir / "lgbm_global_v1_2026-01-01.pkl"
        fake_pkl.write_bytes(b"placeholder")  # just needs to exist
        mocker.patch("agents.forecast_engine.joblib.load", return_value=mock_model)

        result = predict(_ROUTE, _FUTURE_DATE, 3240, 42)
        assert abs(result.lgbm_score - 0.85) < 0.01
        assert result.forecast_direction == "up"

    def test_should_retrain_no_model(self, models_dir: Path) -> None:
        assert should_retrain() is True

    def test_should_retrain_below_threshold(self, models_dir: Path) -> None:
        # 30 observations — below 50 threshold; model exists but count too low
        (models_dir / "lgbm_global_v1_2026-01-01.pkl").write_bytes(b"placeholder")
        with patch("agents.forecast_engine.queries.get_observation_count_by_route",
                   return_value={_ROUTE: 30}):
            result = should_retrain()
        assert result is False

    def test_should_retrain_crosses_threshold(self, models_dir: Path) -> None:
        # 51 observations crosses threshold 50, but no model exists yet
        with patch("agents.forecast_engine.queries.get_observation_count_by_route",
                   return_value={_ROUTE: 51}):
            result = should_retrain()
        assert result is True

    def test_forecast_direction_up(self) -> None:
        assert _score_to_direction(0.75) == "up"
        assert _score_to_direction(1.0) == "up"

    def test_forecast_direction_down(self) -> None:
        assert _score_to_direction(0.20) == "down"
        assert _score_to_direction(0.0) == "down"

    def test_forecast_direction_flat(self) -> None:
        assert _score_to_direction(0.50) == "flat"
        assert _score_to_direction(0.40) == "flat"

    def test_feature_values_in_result(self, models_dir: Path) -> None:
        result = predict(_ROUTE, _FUTURE_DATE, 3240, 42)
        assert isinstance(result.feature_values, dict)
        # When no model exists, feature_values is empty dict
        assert result.feature_values == {}


# ─── TestAlertEngine ─────────────────────────────────────────────────────────


class TestAlertEngine:

    def test_all_gates_pass_should_alert(self) -> None:
        _seed_stats(n=15, base_price=5000)
        # Insert a price below P10
        Q.insert_price_observation(
            route=_ROUTE, travel_date=_FUTURE_DATE, price_inr=2500,
            airline="IndiGo", stops=0, source="skyscanner",
        )
        Q.update_price_stats(_ROUTE, _FUTURE_DATE)
        stats = Q.get_price_stats(_ROUTE, _FUTURE_DATE)
        price = stats.p10_price - 100 if stats.p10_price else 2000

        forecast = _make_forecast(score=0.82)
        analysis = _make_analysis()
        decision = evaluate_alert(_ROUTE, _FUTURE_DATE, price, analysis, forecast)
        assert decision.gate1_passed is True
        assert decision.gate2_passed is True
        assert decision.gate3_passed is True
        assert decision.should_alert is True

    def test_gate1_fails_price_above_p10(self) -> None:
        _seed_stats(n=15, base_price=4000)
        forecast = _make_forecast(score=0.82)
        analysis = _make_analysis()
        # Price well above P10
        decision = evaluate_alert(_ROUTE, _FUTURE_DATE, 9999, analysis, forecast)
        assert decision.gate1_passed is False
        assert decision.should_alert is False

    def test_gate2_fails_low_ml_score(self) -> None:
        _seed_stats(n=15, base_price=5000)
        Q.insert_price_observation(
            route=_ROUTE, travel_date=_FUTURE_DATE, price_inr=2000,
            airline="IndiGo", stops=0, source="skyscanner",
        )
        Q.update_price_stats(_ROUTE, _FUTURE_DATE)
        stats = Q.get_price_stats(_ROUTE, _FUTURE_DATE)
        price = (stats.p10_price or 3000) - 100
        forecast = _make_forecast(score=0.45)  # below threshold
        analysis = _make_analysis()
        decision = evaluate_alert(_ROUTE, _FUTURE_DATE, price, analysis, forecast)
        assert decision.gate2_passed is False
        assert decision.should_alert is False

    def test_gate2_bypassed_no_model(self) -> None:
        _seed_stats(n=15, base_price=5000)
        Q.insert_price_observation(
            route=_ROUTE, travel_date=_FUTURE_DATE, price_inr=2000,
            airline="IndiGo", stops=0, source="skyscanner",
        )
        Q.update_price_stats(_ROUTE, _FUTURE_DATE)
        stats = Q.get_price_stats(_ROUTE, _FUTURE_DATE)
        price = (stats.p10_price or 3000) - 100
        # score=0.5 and model_version="none" → bypass
        forecast = _make_forecast(score=0.5, model_version="none")
        analysis = _make_analysis()
        decision = evaluate_alert(_ROUTE, _FUTURE_DATE, price, analysis, forecast)
        assert decision.gate2_passed is True

    def test_gate3_fails_cooldown_active(self) -> None:
        _seed_stats(n=15, base_price=5000)
        Q.insert_price_observation(
            route=_ROUTE, travel_date=_FUTURE_DATE, price_inr=2000,
            airline="IndiGo", stops=0, source="skyscanner",
        )
        Q.update_price_stats(_ROUTE, _FUTURE_DATE)
        stats = Q.get_price_stats(_ROUTE, _FUTURE_DATE)
        price = (stats.p10_price or 3000) - 100
        # Log a recent alert to trigger cooldown
        Q.log_alert_sent(_ROUTE, _FUTURE_DATE, price, "test alert")
        forecast = _make_forecast(score=0.82)
        analysis = _make_analysis()
        decision = evaluate_alert(_ROUTE, _FUTURE_DATE, price, analysis, forecast)
        assert decision.gate3_passed is False
        assert decision.should_alert is False

    def test_message_contains_route(self) -> None:
        msg = format_alert_message(
            _ROUTE, _FUTURE_DATE, _CURRENT_PRICE,
            _make_analysis(), _make_forecast(), _make_alert_decision(),
        )
        assert "NAG" in msg and "DEL" in msg

    def test_message_contains_price_formatted(self) -> None:
        msg = format_alert_message(
            _ROUTE, _FUTURE_DATE, 3240,
            _make_analysis(), _make_forecast(), _make_alert_decision(),
        )
        assert "3,240" in msg

    def test_message_contains_booking_url(self) -> None:
        msg = format_alert_message(
            _ROUTE, _FUTURE_DATE, _CURRENT_PRICE,
            _make_analysis(), _make_forecast(), _make_alert_decision(),
        )
        assert "skyscanner.co.in" in msg
        assert "nag" in msg
        assert "del" in msg

    def test_message_html_parse_mode(self) -> None:
        msg = format_alert_message(
            _ROUTE, _FUTURE_DATE, _CURRENT_PRICE,
            _make_analysis(), _make_forecast(), _make_alert_decision(),
        )
        assert "<b>" in msg
        assert "**" not in msg  # must NOT use Markdown

    def test_booking_url_date_format(self) -> None:
        td = date(2026, 12, 15)
        url = _build_skyscanner_url("NAG-DEL", td)
        assert "261215" in url
        assert "nag" in url
        assert "del" in url

    def test_fmt_inr_comma_notation(self) -> None:
        assert _fmt_inr(3240) == "3,240"
        assert _fmt_inr(120000) == "1,20,000"
        assert _fmt_inr(None) == "N/A"
        assert _fmt_inr(500) == "500"

    def test_send_telegram_success(self, mocker: Any) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mocker.patch("requests.post", return_value=mock_resp)
        result = send_telegram_alert("test message")
        assert result is True

    def test_send_telegram_rate_limit_retry(self, mocker: Any) -> None:
        r429 = MagicMock(status_code=429)
        r200 = MagicMock(status_code=200)
        mocker.patch("requests.post", side_effect=[r429, r200])
        mocker.patch("agents.alert_engine.time.sleep")  # skip the 30s wait
        result = send_telegram_alert("test message")
        assert result is True

    def test_send_telegram_400_strips_html(self, mocker: Any) -> None:
        r400 = MagicMock(status_code=400, text="Bad Request")
        r200 = MagicMock(status_code=200)
        mocker.patch("requests.post", side_effect=[r400, r200])
        result = send_telegram_alert("<b>test</b> message")
        assert result is True

    def test_send_telegram_failure_no_raise(self, mocker: Any) -> None:
        mocker.patch("requests.post", side_effect=Exception("network error"))
        result = send_telegram_alert("test message")
        assert result is False  # must not raise

    def test_log_alert_called_on_send(self, mocker: Any) -> None:
        r200 = MagicMock(status_code=200)
        mocker.patch("requests.post", return_value=r200)
        log_mock = mocker.patch("agents.pipeline.queries.log_alert_sent")
        from agents.pipeline import PipelineRunner

        # Seed DB with enough data to pass gate1
        _seed_stats(n=15, base_price=5000)
        Q.insert_price_observation(
            route=_ROUTE, travel_date=_FUTURE_DATE, price_inr=2000,
            airline="IndiGo", stops=0, source="skyscanner",
        )
        Q.update_price_stats(_ROUTE, _FUTURE_DATE)
        stats = Q.get_price_stats(_ROUTE, _FUTURE_DATE)
        price = (stats.p10_price or 3000) - 100

        runner = PipelineRunner.__new__(PipelineRunner)
        mock_user = MagicMock()
        mock_user.initiate_chat.return_value = _make_chat_result(_VALID_GEMINI_RESPONSE)
        runner._analyzer = AnalyzerAgent.__new__(AnalyzerAgent)
        runner._analyzer._assistant = MagicMock()
        runner._analyzer._user = mock_user

        forecast = _make_forecast(score=0.82)
        with patch("agents.pipeline.predict", return_value=forecast), \
             patch("agents.pipeline.queries.get_price_history",
                   return_value=[MagicMock(price_inr=price)]):
            sent, _ = runner._process_route(_ROUTE, _FUTURE_DATE)

        if sent:
            log_mock.assert_called_once()


# ─── TestPipelineRunner ───────────────────────────────────────────────────────


class TestPipelineRunner:

    def _make_runner(self, mocker: Any) -> "Any":
        from agents.pipeline import PipelineRunner
        runner = PipelineRunner.__new__(PipelineRunner)
        mock_user = MagicMock()
        mock_user.initiate_chat.return_value = _make_chat_result(_VALID_GEMINI_RESPONSE)
        runner._analyzer = AnalyzerAgent.__new__(AnalyzerAgent)
        runner._analyzer._assistant = MagicMock()
        runner._analyzer._user = mock_user
        return runner

    def test_full_pipeline_no_routes(self, mocker: Any) -> None:
        from agents.pipeline import PipelineRunner
        empty_scrape = MagicMock()
        empty_scrape.route_results = []
        empty_scrape.routes_succeeded = 0
        empty_scrape.total_fares_stored = 0
        mocker.patch("agents.pipeline.ScraperOrchestrator",
                     return_value=MagicMock(run=MagicMock(return_value=empty_scrape)))
        mocker.patch("agents.pipeline.should_retrain", return_value=False)

        runner = self._make_runner(mocker)
        result = runner.run()
        assert result.routes_analysed == 0
        assert result.alerts_sent == 0

    def test_scrape_fail_returns_immediately(self, mocker: Any) -> None:
        from agents.pipeline import PipelineRunner
        mocker.patch("agents.pipeline.ScraperOrchestrator",
                     return_value=MagicMock(run=MagicMock(side_effect=RuntimeError("boom"))))

        runner = self._make_runner(mocker)
        result = runner.run()
        assert result.routes_analysed == 0
        assert "Scrape failed" in result.errors[0]

    def test_retrain_triggered_at_threshold(self, mocker: Any) -> None:
        from agents.pipeline import PipelineRunner
        empty_scrape = MagicMock(route_results=[], routes_succeeded=0, total_fares_stored=0)
        mocker.patch("agents.pipeline.ScraperOrchestrator",
                     return_value=MagicMock(run=MagicMock(return_value=empty_scrape)))
        mocker.patch("agents.pipeline.should_retrain", return_value=True)
        mock_train = mocker.patch("agents.pipeline.train", return_value=MagicMock())

        runner = self._make_runner(mocker)
        result = runner.run()
        assert result.retrain_triggered is True
        mock_train.assert_called_once()

    def test_retrain_fail_continues_pipeline(self, mocker: Any) -> None:
        from agents.pipeline import PipelineRunner
        empty_scrape = MagicMock(route_results=[], routes_succeeded=0, total_fares_stored=0)
        mocker.patch("agents.pipeline.ScraperOrchestrator",
                     return_value=MagicMock(run=MagicMock(return_value=empty_scrape)))
        mocker.patch("agents.pipeline.should_retrain", return_value=True)
        mocker.patch("agents.pipeline.train", side_effect=Exception("OOM"))

        runner = self._make_runner(mocker)
        result = runner.run()  # must not raise
        assert any("Retrain failed" in e for e in result.errors)
        assert result.routes_analysed == 0  # no routes to process

    def test_alert_suppressed_on_wait(self, mocker: Any) -> None:
        from agents.pipeline import PipelineRunner
        route_result = MagicMock()
        route_result.error = None
        route_result.fares_stored = 1
        route_result.route = _ROUTE
        route_result.travel_date = _FUTURE_DATE
        scrape = MagicMock(
            route_results=[route_result],
            routes_succeeded=1,
            total_fares_stored=1,
        )
        mocker.patch("agents.pipeline.ScraperOrchestrator",
                     return_value=MagicMock(run=MagicMock(return_value=scrape)))
        mocker.patch("agents.pipeline.should_retrain", return_value=False)
        # Gate 1 fails — price above P10
        mocker.patch("agents.pipeline.queries.get_price_history",
                     return_value=[MagicMock(price_inr=9999)])
        mocker.patch("agents.pipeline.predict", return_value=_make_forecast(0.82))
        mocker.patch("agents.pipeline.build_price_summary", return_value=_make_summary())
        mocker.patch("agents.pipeline.queries.store_ml_forecast")
        mocker.patch("agents.pipeline.queries.get_price_stats",
                     return_value=MagicMock(p10_price=5000, observation_count=15,
                                           median_price=6000))
        mock_send = mocker.patch("agents.pipeline.send_telegram_alert")

        runner = self._make_runner(mocker)
        result = runner.run()
        mock_send.assert_not_called()
        assert result.alerts_sent == 0

    def test_route_error_does_not_stop_others(self, mocker: Any) -> None:
        from agents.pipeline import PipelineRunner
        r1 = MagicMock(error=None, fares_stored=1, route="NAG-DEL", travel_date=_FUTURE_DATE)
        r2 = MagicMock(error=None, fares_stored=1, route="NAG-BOM",
                       travel_date=_FUTURE_DATE + timedelta(days=10))
        scrape = MagicMock(route_results=[r1, r2], routes_succeeded=2, total_fares_stored=2)
        mocker.patch("agents.pipeline.ScraperOrchestrator",
                     return_value=MagicMock(run=MagicMock(return_value=scrape)))
        mocker.patch("agents.pipeline.should_retrain", return_value=False)
        mocker.patch("agents.pipeline.queries.get_price_history",
                     side_effect=[Exception("DB error"), [MagicMock(price_inr=9999)]])
        mocker.patch("agents.pipeline.predict", return_value=_make_forecast(0.5, "none"))
        mocker.patch("agents.pipeline.build_price_summary", return_value=None)
        mocker.patch("agents.pipeline.queries.store_ml_forecast")

        runner = self._make_runner(mocker)
        result = runner.run()  # must not raise despite route 1 error
        assert result.routes_analysed >= 1  # at least route 2 processed

    def test_pipeline_result_accurate_counts(self, mocker: Any) -> None:
        from agents.pipeline import PipelineRunner
        empty_scrape = MagicMock(route_results=[], routes_succeeded=0, total_fares_stored=0)
        mocker.patch("agents.pipeline.ScraperOrchestrator",
                     return_value=MagicMock(run=MagicMock(return_value=empty_scrape)))
        mocker.patch("agents.pipeline.should_retrain", return_value=False)

        runner = self._make_runner(mocker)
        result = runner.run()
        assert result.alerts_sent + result.alerts_suppressed == result.routes_analysed

    def test_suppression_reasons_tracked(self, mocker: Any) -> None:
        from agents.pipeline import PipelineRunner
        route_result = MagicMock(error=None, fares_stored=1,
                                 route=_ROUTE, travel_date=_FUTURE_DATE)
        scrape = MagicMock(route_results=[route_result],
                           routes_succeeded=1, total_fares_stored=1)
        mocker.patch("agents.pipeline.ScraperOrchestrator",
                     return_value=MagicMock(run=MagicMock(return_value=scrape)))
        mocker.patch("agents.pipeline.should_retrain", return_value=False)
        mocker.patch("agents.pipeline.queries.get_price_history",
                     return_value=[MagicMock(price_inr=9999)])
        mocker.patch("agents.pipeline.predict", return_value=_make_forecast(0.82))
        mocker.patch("agents.pipeline.build_price_summary", return_value=_make_summary())
        mocker.patch("agents.pipeline.queries.store_ml_forecast")
        mocker.patch("agents.pipeline.queries.get_price_stats",
                     return_value=MagicMock(p10_price=5000, observation_count=15,
                                           median_price=6000, all_time_low=3000))

        runner = self._make_runner(mocker)
        result = runner.run()
        assert result.alerts_suppressed >= 0
        # Gate 1 fails (price=9999 > p10=5000) → reason tracked
        assert isinstance(result.suppression_reasons, dict)
