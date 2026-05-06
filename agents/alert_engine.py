"""agents/alert_engine.py — Phase 3 Subsystem C: Telegram Alert Engine.

The ONLY module permitted to send Telegram messages. Enforces all three
alert gates and formats beautifully structured HTML messages with full
evidence chain. Logs every sent and suppressed alert.

Three-gate decision:
  Gate 1 (Statistical):  current_price <= P10 AND observation_count >= 10
  Gate 2 (ML):           lgbm_score >= 0.70 (or bypassed if no model trained)
  Gate 3 (Cooldown):     no alert sent in last 24 hours

ALL THREE must pass for should_alert=True.

Logger name: flight_agent.alert
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from agents.base_agent import get_logger, utcnow
from agents.analyzer_agent import AnalysisReport
from agents.forecast_engine import ForecastScore
import db.queries as queries

# ─── MODULE LOGGER ────────────────────────────────────────────────────────────

_log = get_logger("flight_agent.alert", "alert.log")

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

ML_SCORE_THRESHOLD: float = 0.70
_NEUTRAL_SCORE: float = 0.5   # score returned when no model exists
_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
_REQUEST_TIMEOUT = 10          # seconds
_RATE_LIMIT_WAIT = 30          # seconds to wait on HTTP 429

# ─── DATACLASSES ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AlertDecision:
    """Result of the three-gate evaluation for one route+date."""

    should_alert: bool
    gate1_passed: bool
    gate2_passed: bool
    gate3_passed: bool
    gate1_reason: str
    gate2_reason: str
    gate3_reason: str
    current_price: int
    p10_price: Optional[int]
    lgbm_score: float
    pct_below_median: Optional[float]
    all_time_low: Optional[int]


# ─── ALERT ENGINE CLASS ───────────────────────────────────────────────────────


class AlertEngine:
    """
    Class-based facade over the module-level alert functions.

    Supports both import styles:
        from agents.alert_engine import AlertEngine       # class
        from agents.alert_engine import evaluate_alert    # functions

    All methods delegate directly to the module-level implementations.
    """

    def evaluate(
        self,
        route: str,
        travel_date: "date",
        current_price: int,
        analysis: "AnalysisReport",
        forecast: "ForecastScore",
    ) -> "AlertDecision":
        """Run the three-gate evaluation. Returns AlertDecision."""
        return evaluate_alert(route, travel_date, current_price, analysis, forecast)

    def format_message(
        self,
        route: str,
        travel_date: "date",
        current_price: int,
        analysis: "AnalysisReport",
        forecast: "ForecastScore",
        alert_decision: "AlertDecision",
    ) -> str:
        """Build the HTML-formatted Telegram message string."""
        return format_alert_message(route, travel_date, current_price, analysis, forecast, alert_decision)

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message via Telegram Bot API. Never raises. Returns True on success."""
        return send_telegram_alert(message, parse_mode)

    def send_test(self) -> bool:
        """Send a connectivity test message to verify bot token and chat ID."""
        return send_test_message()


# ─── THREE-GATE EVALUATION ────────────────────────────────────────────────────



def evaluate_alert(
    route: str,
    travel_date: date,
    current_price: int,
    analysis: AnalysisReport,
    forecast: ForecastScore,
) -> AlertDecision:
    """
    Evaluate whether all three gates pass for an alert.

    Gate 1 — Statistical gate (uses queries.get_alert_decision):
      Passes if current_price <= P10 AND observation_count >= 10.

    Gate 2 — ML gate:
      Passes if forecast.lgbm_score >= ML_SCORE_THRESHOLD (0.70).
      If no model exists (lgbm_score == 0.5 exactly): Gate 2 PASSES with warning.

    Gate 3 — Cooldown gate (uses queries.check_alert_cooldown):
      Passes if no alert was sent in the last 24 hours.

    ALL THREE must pass for should_alert=True.
    """
    # ── Gate 1: Statistical check via existing Phase 1 logic ──────────────
    try:
        stat_decision = queries.get_alert_decision(
            route=route,
            travel_date=travel_date,
            current_price=current_price,
        )
        gate1_passed = stat_decision.should_alert
        gate1_reason = stat_decision.reason
        p10_price = stat_decision.p10_price
        all_time_low = stat_decision.all_time_low
        pct_below_median = stat_decision.pct_below_median
    except Exception as exc:
        gate1_passed = False
        gate1_reason = f"Gate 1 evaluation error: {exc}"
        p10_price = None
        all_time_low = None
        pct_below_median = None

    _log.info(
        json.dumps({
            "event": "gate1_evaluated",
            "route": route,
            "travel_date": travel_date.isoformat(),
            "passed": gate1_passed,
            "reason": gate1_reason,
        })
    )

    # ── Gate 2: ML score check ─────────────────────────────────────────────
    lgbm_score = forecast.lgbm_score

    if lgbm_score == _NEUTRAL_SCORE and forecast.model_version == "none":
        gate2_passed = True
        gate2_reason = "ML model not trained yet — Gate 2 bypassed for this run."
        _log.warning(
            json.dumps({
                "event": "gate2_bypassed",
                "route": route,
                "travel_date": travel_date.isoformat(),
                "reason": gate2_reason,
            })
        )
    elif lgbm_score >= ML_SCORE_THRESHOLD:
        gate2_passed = True
        gate2_reason = f"ML score {lgbm_score:.3f} >= threshold {ML_SCORE_THRESHOLD}"
    else:
        gate2_passed = False
        gate2_reason = f"ML score {lgbm_score:.3f} < threshold {ML_SCORE_THRESHOLD}"

    _log.info(
        json.dumps({
            "event": "gate2_evaluated",
            "route": route,
            "travel_date": travel_date.isoformat(),
            "passed": gate2_passed,
            "lgbm_score": lgbm_score,
            "reason": gate2_reason,
        })
    )

    # ── Gate 3: Cooldown check ─────────────────────────────────────────────
    try:
        is_cooling, hours_ago = queries.check_alert_cooldown(route, travel_date)
        if is_cooling:
            gate3_passed = False
            gate3_reason = (
                f"Alert already sent {hours_ago:.1f}h ago (cooldown: 24h)"
                if hours_ago is not None
                else "Alert sent recently (cooldown active)"
            )
        else:
            gate3_passed = True
            gate3_reason = "No recent alert — cooldown clear"
    except Exception as exc:
        gate3_passed = False
        gate3_reason = f"Gate 3 evaluation error: {exc}"

    _log.info(
        json.dumps({
            "event": "gate3_evaluated",
            "route": route,
            "travel_date": travel_date.isoformat(),
            "passed": gate3_passed,
            "reason": gate3_reason,
        })
    )

    should_alert = gate1_passed and gate2_passed and gate3_passed

    if not should_alert:
        failed_gates = []
        if not gate1_passed:
            failed_gates.append(f"Gate1: {gate1_reason}")
        if not gate2_passed:
            failed_gates.append(f"Gate2: {gate2_reason}")
        if not gate3_passed:
            failed_gates.append(f"Gate3: {gate3_reason}")
        _log.info(
            json.dumps({
                "event": "alert_suppressed",
                "route": route,
                "travel_date": travel_date.isoformat(),
                "failed_gates": failed_gates,
            })
        )

    return AlertDecision(
        should_alert=should_alert,
        gate1_passed=gate1_passed,
        gate2_passed=gate2_passed,
        gate3_passed=gate3_passed,
        gate1_reason=gate1_reason,
        gate2_reason=gate2_reason,
        gate3_reason=gate3_reason,
        current_price=current_price,
        p10_price=p10_price,
        lgbm_score=lgbm_score,
        pct_below_median=pct_below_median,
        all_time_low=all_time_low,
    )


# ─── FORMATTING HELPERS ───────────────────────────────────────────────────────


def _fmt_inr(price: Optional[int]) -> str:
    """Format a price with Indian comma notation. e.g. 3240 → '3,240'."""
    if price is None:
        return "N/A"
    # Indian numbering: last 3 digits, then groups of 2
    s = str(price)
    if len(s) <= 3:
        return s
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return result.lstrip(",")


def _build_skyscanner_url(route: str, travel_date: date) -> str:
    """Build a Skyscanner deep-link URL for the given route and travel date."""
    parts = route.split("-")
    if len(parts) != 2:
        return "https://www.skyscanner.co.in"
    origin_lower = parts[0].lower()
    dest_lower = parts[1].lower()
    # Date format: YYMMDD  e.g. 2026-12-15 → 261215
    date_str = travel_date.strftime("%y%m%d")
    return (
        f"https://www.skyscanner.co.in/transport/flights/"
        f"{origin_lower}/{dest_lower}/{date_str}/"
    )


def _format_route_display(route: str) -> str:
    """Format 'NAG-DEL' as 'NAG → DEL'."""
    return route.replace("-", " → ")


def _format_alert_timestamp() -> str:
    """Return current time formatted as '03 May 2026, 06:30 IST'."""
    ist_offset = 5 * 3600 + 30 * 60  # UTC+5:30
    now_utc = utcnow()
    # Compute IST manually to avoid pytz dependency
    from datetime import timedelta
    now_ist = now_utc + timedelta(seconds=ist_offset)
    return now_ist.strftime("%d %b %Y, %H:%M IST")


# ─── MESSAGE FORMATTER ────────────────────────────────────────────────────────


def format_alert_message(
    route: str,
    travel_date: date,
    current_price: int,
    analysis: AnalysisReport,
    forecast: ForecastScore,
    alert_decision: AlertDecision,
) -> str:
    """
    Build a beautifully formatted Telegram message string (HTML parse mode).

    Uses <b> and <i> HTML tags — NOT Markdown ** syntax.
    Includes: route, travel date, current price, P10, all-time low, median,
    savings %, AI insight, ML forecast score, recommendation, and booking URL.
    """
    sep = "━━━━━━━━━━━━━━━━━━━━━━"
    route_display = _format_route_display(route)
    travel_date_str = travel_date.strftime("%d %B %Y")
    days_away = (travel_date - date.today()).days
    booking_url = _build_skyscanner_url(route, travel_date)

    # Price lines
    price_str = _fmt_inr(current_price)
    p10_str = _fmt_inr(alert_decision.p10_price)
    atl_str = _fmt_inr(alert_decision.all_time_low)

    # Median — try to get from DB for the message
    median_str = "N/A"
    try:
        stats = queries.get_price_stats(route, travel_date)
        if stats and stats.median_price:
            median_str = _fmt_inr(stats.median_price)
    except Exception:
        pass

    # Saving vs median
    pct = alert_decision.pct_below_median
    saving_str = f"{pct:+.1f}%" if pct is not None else "N/A"

    # ML forecast line
    direction_label = {
        "up": "RISE ↑",
        "down": "FALL ↓",
        "flat": "STABLE →",
    }.get(forecast.forecast_direction, forecast.forecast_direction.upper())
    ml_line = f"Price likely to {direction_label} (score: {forecast.lgbm_score:.2f})"

    # Recommendation & confidence
    rec_display = analysis.recommendation.replace("_", " ")
    conf_display = analysis.confidence

    timestamp_str = _format_alert_timestamp()

    msg = (
        f"✈️ <b>FLIGHT DEAL ALERT</b>\n"
        f"{sep}\n"
        f"🛫 <b>Route:</b> {route_display}\n"
        f"📅 <b>Travel Date:</b> {travel_date_str} ({days_away} days away)\n"
        f"{sep}\n"
        f"💰 <b>Current Price:  ₹{price_str}</b>\n"
        f"📊 <b>Historical P10: ₹{p10_str}</b>\n"
        f"📉 <b>All-Time Low:   ₹{atl_str}</b>\n"
        f"📈 <b>Median Price:   ₹{median_str}</b>\n"
        f"🎯 <b>Saving vs Median: {saving_str}</b>\n"
        f"{sep}\n"
        f"🤖 <b>AI Insight:</b>\n"
        f"<i>{analysis.key_insight}</i>\n\n"
        f"📡 <b>ML Forecast:</b> {ml_line}\n"
        f"🧠 <b>Recommendation:</b> {rec_display} ({conf_display} confidence)\n"
        f"{sep}\n"
        f'🔗 <a href="{booking_url}">Search on Skyscanner</a>\n'
        f"⏰ Alert generated: {timestamp_str}"
    )

    return msg


# ─── TELEGRAM SENDER ─────────────────────────────────────────────────────────


def _strip_html(text: str) -> str:
    """Remove all HTML tags from a string for plain-text fallback."""
    return re.sub(r"<[^>]+>", "", text)


def send_telegram_alert(
    message: str,
    parse_mode: str = "HTML",
) -> bool:
    """
    Send message to Telegram via Bot API.

    On HTTP 200: log INFO, return True.
    On HTTP 429: wait 30s, retry once. Log WARNING.
    On HTTP 400: strip HTML tags, retry once with plain text. Log ERROR.
    On any other error: log ERROR, return False. Never raises.

    Timeout: 10 seconds on each requests.post() call.
    """
    import requests  # type: ignore[import-untyped]

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        _log.error(
            json.dumps({
                "event": "telegram_send_failed",
                "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set",
            })
        )
        return False

    url = _TELEGRAM_API_BASE.format(token=bot_token)

    def _post(text: str, mode: str) -> "requests.Response":
        return requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": mode,
                "disable_web_page_preview": False,
            },
            timeout=_REQUEST_TIMEOUT,
        )

    try:
        resp = _post(message, parse_mode)

        if resp.status_code == 200:
            _log.warning(
                json.dumps({
                    "event": "telegram_alert_sent",
                    "chat_id": chat_id,
                    "message_length": len(message),
                })
            )
            return True

        if resp.status_code == 429:
            _log.warning(
                json.dumps({
                    "event": "telegram_rate_limited",
                    "retry_after_seconds": _RATE_LIMIT_WAIT,
                })
            )
            time.sleep(_RATE_LIMIT_WAIT)
            retry_resp = _post(message, parse_mode)
            if retry_resp.status_code == 200:
                _log.warning(
                    json.dumps({
                        "event": "telegram_alert_sent",
                        "attempt": 2,
                        "chat_id": chat_id,
                    })
                )
                return True
            _log.error(
                json.dumps({
                    "event": "telegram_send_failed",
                    "status": retry_resp.status_code,
                    "body": retry_resp.text[:300],
                })
            )
            return False

        if resp.status_code == 400:
            _log.error(
                json.dumps({
                    "event": "telegram_bad_request",
                    "status": 400,
                    "body": resp.text[:300],
                    "action": "stripping HTML and retrying",
                })
            )
            plain_text = _strip_html(message)
            retry_resp = _post(plain_text, "")
            if retry_resp.status_code == 200:
                _log.warning(
                    json.dumps({
                        "event": "telegram_alert_sent",
                        "attempt": 2,
                        "mode": "plain_text",
                        "chat_id": chat_id,
                    })
                )
                return True
            _log.error(
                json.dumps({
                    "event": "telegram_send_failed",
                    "status": retry_resp.status_code,
                    "body": retry_resp.text[:300],
                })
            )
            return False

        _log.error(
            json.dumps({
                "event": "telegram_send_failed",
                "status": resp.status_code,
                "body": resp.text[:300],
            })
        )
        return False

    except Exception as exc:
        _log.error(
            json.dumps({
                "event": "telegram_send_exception",
                "error": str(exc),
            })
        )
        return False


def send_test_message() -> bool:
    """
    Send a simple test message to verify bot token and chat ID are correct.
    Called once during Phase 3 setup verification.

    Returns True if sent successfully.
    """
    msg = "✅ SkySaver bot connected successfully. Monitoring active."
    return send_telegram_alert(msg, parse_mode="HTML")
