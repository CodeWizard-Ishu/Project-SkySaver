"""agents/analyzer_agent.py — Phase 3 Subsystem A: AnalyzerAgent.

Uses Gemini 2.5 Pro (adaptive thinking) via AG2 ConversableAgent to reason
about flight price history and produce a structured AnalysisReport for every
route+date pair that received new data after a scrape run.

The agent is NOT rule-based — it reasons about context such as seasonal spikes,
thin datasets, and booking timing. Rule-based alerting (Gates 1–3) lives in
alert_engine.py. The AnalysisReport provides qualitative context that enriches
the Telegram alert message.

Logger name: flight_agent.analyzer
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Optional

from agents.base_agent import get_gemini_pro_config, get_logger, utcnow
import db.queries as queries

# ─── MODULE LOGGER ────────────────────────────────────────────────────────────

_log = get_logger("flight_agent.analyzer", "analyzer.log")

# ─── DATACLASSES ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PriceSummary:
    """Structured price context for one route+date pair, fed to the AnalyzerAgent."""

    route: str
    travel_date: date
    current_price: int
    p10_price: Optional[int]
    p25_price: Optional[int]
    median_price: Optional[int]
    all_time_low: Optional[int]
    all_time_high: Optional[int]
    observation_count: int
    pct_vs_median: Optional[float]      # negative = cheaper than median
    pct_vs_p10: Optional[float]         # negative = cheaper than P10
    lgbm_score: Optional[float]         # from latest ml_forecast
    forecast_direction: Optional[str]   # "up" | "down" | "flat"
    days_until_travel: int
    recent_7d_prices: list[int]         # last 7 days of observed prices, ascending


@dataclass(frozen=True)
class AnalysisReport:
    """Structured reasoning output from Gemini 2.5 Pro for one route+date."""

    route: str
    travel_date: date
    recommendation: str         # "BUY_NOW" | "WAIT" | "MONITOR" | "INSUFFICIENT_DATA"
    confidence: str             # "HIGH" | "MEDIUM" | "LOW"
    reasoning: str              # 2-4 sentence natural language explanation
    urgency_score: int          # 1–10: how time-sensitive is the decision?
    key_insight: str            # one punchy sentence for the Telegram headline
    generated_at: datetime      # UTC timestamp
    model_version: str          # "gemini-2.5-pro"


# ─── VALID VALUES ─────────────────────────────────────────────────────────────

_VALID_RECOMMENDATIONS = frozenset({"BUY_NOW", "WAIT", "MONITOR", "INSUFFICIENT_DATA"})
_VALID_CONFIDENCES = frozenset({"HIGH", "MEDIUM", "LOW"})

# ─── FALLBACK REPORT ─────────────────────────────────────────────────────────


def _fallback_report(route: str, travel_date: date, reason: str) -> AnalysisReport:
    """Return a safe fallback AnalysisReport when Gemini cannot be reached or parsed."""
    return AnalysisReport(
        route=route,
        travel_date=travel_date,
        recommendation="INSUFFICIENT_DATA",
        confidence="LOW",
        reasoning=reason,
        urgency_score=1,
        key_insight="Analysis unavailable.",
        generated_at=utcnow(),
        model_version="gemini-2.5-pro",
    )


# ─── ANALYZER AGENT ──────────────────────────────────────────────────────────


class AnalyzerAgent:
    """
    Wraps Gemini 2.5 Pro in an AG2 ConversableAgent for flight price reasoning.

    The agent receives a PriceSummary as a structured prompt and returns
    a JSON object matching the AnalysisReport schema. The prompt is
    engineered so the model ALWAYS returns valid JSON — never prose.

    One agent instance is reused across all route analyses in a pipeline run.
    The AG2 conversation is reset between routes (clear_history=True).
    """

    SYSTEM_PROMPT: str = """
You are a flight price analyst AI. Your job is to evaluate whether a
current flight price represents a genuine buying opportunity.

You will receive a JSON object containing price statistics for one
flight route. You must respond with ONLY a valid JSON object matching
this exact schema — no prose, no markdown, no explanation outside the JSON:

{
  "recommendation": "<BUY_NOW|WAIT|MONITOR|INSUFFICIENT_DATA>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "reasoning": "<2-4 sentences explaining your decision>",
  "urgency_score": <integer 1-10>,
  "key_insight": "<one punchy sentence, max 15 words>"
}

Decision guidelines:
- BUY_NOW:            price <= P10 AND lgbm_score >= 0.70 AND travel >= 14 days away
- WAIT:               price > median OR travel > 180 days (too early)
- MONITOR:            price between P10 and P25, OR lgbm_score < 0.70
- INSUFFICIENT_DATA:  fewer than 10 observations OR no P10 computed yet

urgency_score rules:
- 9-10: price <= all_time_low AND travel <= 30 days
- 7-8:  price <= P10 AND lgbm says UP AND travel 30-90 days
- 5-6:  price <= P25, mixed signals
- 3-4:  monitoring territory, no urgency
- 1-2:  wait, price is high or too early to book

Always consider days_until_travel in your reasoning. A price at P10 with
only 5 days until travel is NOT a good deal — prices always spike last-minute.
The sweet spot for Indian domestic routes is 30–90 days in advance.
""".strip()

    def __init__(self) -> None:
        self._llm_config = get_gemini_pro_config()
        self._assistant: "Any" = None
        self._user: "Any" = None
        self._build_agents()

    def _build_agents(self) -> None:
        """Construct the AG2 ConversableAgent pair (assistant + user proxy)."""
        try:
            from autogen import ConversableAgent  # type: ignore[import-untyped]

            self._assistant = ConversableAgent(
                name="flight_price_analyst",
                system_message=self.SYSTEM_PROMPT,
                llm_config=self._llm_config,
                human_input_mode="NEVER",
                max_consecutive_auto_reply=1,
            )
            self._user = ConversableAgent(
                name="pipeline_driver",
                llm_config=False,
                human_input_mode="NEVER",
                max_consecutive_auto_reply=0,
            )
            _log.info(
                json.dumps({
                    "event": "analyzer_agent_initialized",
                    "model": "gemini-2.5-pro",
                })
            )
        except Exception as exc:
            _log.error(
                json.dumps({
                    "event": "analyzer_agent_init_failed",
                    "error": str(exc),
                })
            )
            self._assistant = None
            self._user = None

    def analyse(self, summary: PriceSummary) -> AnalysisReport:
        """
        Run Gemini 2.5 Pro reasoning on one PriceSummary.

        Builds a user message containing the summary as formatted JSON,
        initiates a single-turn AG2 conversation, parses the JSON response,
        and returns a populated AnalysisReport.

        Retry: if Gemini returns invalid JSON, retry once with an explicit
        "Return ONLY valid JSON, nothing else." prefix added to the message.
        If second attempt also fails: return a fallback AnalysisReport with
        recommendation="INSUFFICIENT_DATA", confidence="LOW",
        reasoning="Analyzer model returned unparseable response.",
        urgency_score=1, key_insight="Analysis unavailable."

        Never raises. Always returns an AnalysisReport.

        Args:
            summary: PriceSummary dataclass for one route+date
        Returns:
            AnalysisReport with reasoning and recommendation
        Side effects:
            Logs the Gemini response at DEBUG level (first 500 chars only)
        """
        if self._assistant is None or self._user is None:
            _log.warning(
                json.dumps({
                    "event": "analyzer_agent_not_initialized",
                    "route": summary.route,
                    "travel_date": summary.travel_date.isoformat(),
                })
            )
            return _fallback_report(
                summary.route,
                summary.travel_date,
                "Analyzer model returned unparseable response.",
            )

        message = self._build_message(summary)

        # Attempt 1 — normal prompt
        raw_response = self._invoke_agent(message)
        if raw_response is not None:
            report = self._parse_response(raw_response, summary)
            if report is not None:
                return report

        # Attempt 2 — explicit JSON-only prefix
        retry_message = "Return ONLY valid JSON, nothing else.\n\n" + message
        raw_response = self._invoke_agent(retry_message)
        if raw_response is not None:
            report = self._parse_response(raw_response, summary)
            if report is not None:
                return report

        _log.warning(
            json.dumps({
                "event": "analyzer_both_attempts_failed",
                "route": summary.route,
                "travel_date": summary.travel_date.isoformat(),
            })
        )
        return _fallback_report(
            summary.route,
            summary.travel_date,
            "Analyzer model returned unparseable response.",
        )

    def _build_message(self, summary: PriceSummary) -> str:
        """Serialize a PriceSummary to a JSON string for the agent prompt."""
        payload = {
            "route": summary.route,
            "travel_date": summary.travel_date.isoformat(),
            "current_price_inr": summary.current_price,
            "p10_price": summary.p10_price,
            "p25_price": summary.p25_price,
            "median_price": summary.median_price,
            "all_time_low": summary.all_time_low,
            "all_time_high": summary.all_time_high,
            "observation_count": summary.observation_count,
            "pct_vs_median": round(summary.pct_vs_median, 2) if summary.pct_vs_median is not None else None,
            "pct_vs_p10": round(summary.pct_vs_p10, 2) if summary.pct_vs_p10 is not None else None,
            "lgbm_score": summary.lgbm_score,
            "forecast_direction": summary.forecast_direction,
            "days_until_travel": summary.days_until_travel,
            "recent_7d_prices": summary.recent_7d_prices,
        }
        return json.dumps(payload, indent=2)

    def _invoke_agent(self, message: str) -> Optional[str]:
        """
        Initiate a single-turn AG2 conversation and return the assistant's reply.

        Returns None if the AG2 call raises any exception.
        """
        try:
            # Reset conversation history between invocations to avoid context bleed
            self._assistant.clear_history()  # type: ignore[union-attr]
            self._user.clear_history()  # type: ignore[union-attr]

            result = self._user.initiate_chat(  # type: ignore[union-attr]
                self._assistant,
                message=message,
                max_turns=1,
                clear_history=True,
            )
            # AG2 ChatResult: last reply is in result.summary or result.chat_history[-1]
            raw = None
            if hasattr(result, "summary") and result.summary:
                raw = str(result.summary)
            elif hasattr(result, "chat_history") and result.chat_history:
                last = result.chat_history[-1]
                raw = last.get("content", "") if isinstance(last, dict) else str(last)

            _log.debug(
                json.dumps({
                    "event": "gemini_response_received",
                    "snippet": (raw or "")[:500],
                })
            )
            return raw
        except Exception as exc:
            _log.error(
                json.dumps({
                    "event": "gemini_invocation_failed",
                    "error": str(exc),
                })
            )
            return None

    def _parse_response(
        self, raw: str, summary: PriceSummary
    ) -> Optional[AnalysisReport]:
        """
        Parse the Gemini JSON response into an AnalysisReport.

        Returns None if JSON is invalid or required fields are missing/invalid.
        """
        try:
            # Strip markdown code fences if model wraps output
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                import re
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```\s*$", "", cleaned)
                cleaned = cleaned.strip()

            # Extract JSON object if surrounded by prose
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start : end + 1]

            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as exc:
            _log.debug(
                json.dumps({
                    "event": "gemini_json_parse_failed",
                    "error": str(exc),
                    "snippet": raw[:200],
                })
            )
            return None

        # Validate required fields
        try:
            recommendation = str(data.get("recommendation", "INSUFFICIENT_DATA")).upper()
            if recommendation not in _VALID_RECOMMENDATIONS:
                recommendation = "INSUFFICIENT_DATA"

            confidence = str(data.get("confidence", "LOW")).upper()
            if confidence not in _VALID_CONFIDENCES:
                confidence = "LOW"

            reasoning = str(data.get("reasoning", "No reasoning provided."))

            urgency_raw = data.get("urgency_score", 1)
            try:
                urgency_score = max(1, min(10, int(urgency_raw)))
            except (TypeError, ValueError):
                urgency_score = 1

            key_insight = str(data.get("key_insight", "Analysis unavailable."))

            return AnalysisReport(
                route=summary.route,
                travel_date=summary.travel_date,
                recommendation=recommendation,
                confidence=confidence,
                reasoning=reasoning,
                urgency_score=urgency_score,
                key_insight=key_insight,
                generated_at=utcnow(),
                model_version="gemini-2.5-pro",
            )
        except Exception as exc:
            _log.debug(
                json.dumps({
                    "event": "gemini_response_field_error",
                    "error": str(exc),
                })
            )
            return None


# ─── HELPER: BUILD PRICE SUMMARY FROM DB ─────────────────────────────────────


def build_price_summary(
    route: str,
    travel_date: date,
    current_price: Optional[int] = None,
) -> Optional[PriceSummary]:
    """
    Fetch all required data from the DB and construct a PriceSummary.

    Calls:
      queries.get_price_stats(route, travel_date)
      queries.get_price_history(route, travel_date, days_back=7)
      queries.get_latest_ml_forecast(route, travel_date)

    Args:
        route: Route string e.g. "NAG-DEL"
        travel_date: Departure date
        current_price: If None, uses the most recent price from history

    Returns:
        PriceSummary or None if no price_stats exist yet for this route+date.
    """
    try:
        stats = queries.get_price_stats(route, travel_date)
    except Exception as exc:
        _log.error(
            json.dumps({
                "event": "build_price_summary_stats_failed",
                "route": route,
                "travel_date": travel_date.isoformat(),
                "error": str(exc),
            })
        )
        return None

    if stats is None:
        _log.debug(
            json.dumps({
                "event": "build_price_summary_no_stats",
                "route": route,
                "travel_date": travel_date.isoformat(),
            })
        )
        return None

    # Fetch last 7 days of price history
    try:
        history = queries.get_price_history(route, travel_date, days_back=7)
    except Exception as exc:
        _log.error(
            json.dumps({
                "event": "build_price_summary_history_failed",
                "route": route,
                "travel_date": travel_date.isoformat(),
                "error": str(exc),
            })
        )
        history = []

    recent_7d_prices = sorted(obs.price_inr for obs in history)

    # Determine current price
    if current_price is None:
        if recent_7d_prices:
            current_price = recent_7d_prices[-1]  # most recent = highest index after sort
            # Re-fetch to get the actual last-scraped price (not sorted min)
            # Use the most recent observation by time
            if history:
                current_price = history[-1].price_inr  # history is sorted ASC by observed_at
        else:
            _log.warning(
                json.dumps({
                    "event": "build_price_summary_no_history",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                })
            )
            return None

    # Fetch latest ML forecast
    try:
        forecast = queries.get_latest_ml_forecast(route, travel_date)
    except Exception as exc:
        _log.error(
            json.dumps({
                "event": "build_price_summary_forecast_failed",
                "route": route,
                "travel_date": travel_date.isoformat(),
                "error": str(exc),
            })
        )
        forecast = None

    lgbm_score = forecast.lgbm_score if forecast else None
    forecast_direction = forecast.forecast_direction if forecast else None

    # Compute percentage deltas
    pct_vs_median: Optional[float] = None
    if stats.median_price and stats.median_price > 0:
        pct_vs_median = ((current_price - stats.median_price) / stats.median_price) * 100.0

    pct_vs_p10: Optional[float] = None
    if stats.p10_price and stats.p10_price > 0:
        pct_vs_p10 = ((current_price - stats.p10_price) / stats.p10_price) * 100.0

    days_until_travel = (travel_date - date.today()).days

    _log.info(
        json.dumps({
            "event": "price_summary_built",
            "route": route,
            "travel_date": travel_date.isoformat(),
            "current_price": current_price,
            "observation_count": stats.observation_count,
            "days_until_travel": days_until_travel,
        })
    )

    return PriceSummary(
        route=route,
        travel_date=travel_date,
        current_price=current_price,
        p10_price=stats.p10_price,
        p25_price=stats.p25_price,
        median_price=stats.median_price,
        all_time_low=stats.all_time_low,
        all_time_high=stats.all_time_high,
        observation_count=stats.observation_count,
        pct_vs_median=pct_vs_median,
        pct_vs_p10=pct_vs_p10,
        lgbm_score=lgbm_score,
        forecast_direction=forecast_direction,
        days_until_travel=days_until_travel,
        recent_7d_prices=recent_7d_prices,
    )
