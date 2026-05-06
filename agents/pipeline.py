"""agents/pipeline.py — Phase 3 Pipeline Orchestrator.

Single entry point called after every scrape run. Wires together:
  Phase 2 ScraperOrchestrator → ForecastEngine → AnalyzerAgent → AlertEngine

Lifecycle (per run):
  1. Scrape all active routes via ScraperOrchestrator
  2. Check if retrain needed; retrain if yes
  3. Predict lgbm_score for each route+date with new data
  4. Store forecasts in ml_forecasts table
  5. Build PriceSummary and run AnalyzerAgent for each route+date
  6. Evaluate three gates via AlertEngine
  7. Send Telegram alert if all three gates pass
  8. Log alert and return PipelineRunResult

Error isolation: one route failing NEVER stops others. Subsystem failures
degrade gracefully with logged errors and neutral fallbacks.

Logger name: flight_agent.pipeline
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from agents.base_agent import get_logger, utcnow
from agents.analyzer_agent import AnalyzerAgent, AnalysisReport, build_price_summary
from agents.forecast_engine import (
    ForecastScore,
    TrainingResult,
    predict,
    should_retrain,
    train,
)
from agents.alert_engine import (
    AlertDecision,
    evaluate_alert,
    format_alert_message,
    send_telegram_alert,
)
from agents.scraper_agent import ScraperOrchestrator, ScrapeRunResult
import db.queries as queries

# ─── MODULE LOGGER ────────────────────────────────────────────────────────────

_log = get_logger("flight_agent.pipeline", "pipeline.log")

# ─── DATACLASSES ─────────────────────────────────────────────────────────────


@dataclass
class PipelineRunResult:
    """Aggregated result of one complete pipeline run."""

    started_at: datetime
    finished_at: datetime
    scrape_result: ScrapeRunResult
    retrain_triggered: bool
    retrain_result: Optional[TrainingResult]
    routes_analysed: int
    alerts_sent: int
    alerts_suppressed: int
    suppression_reasons: dict[str, int]   # gate failure reason → count
    errors: list[str]
    total_duration_seconds: float


# ─── PIPELINE RUNNER ─────────────────────────────────────────────────────────


class PipelineRunner:
    """
    Orchestrates a complete SkySaver pipeline run.

    One instance per run. The AnalyzerAgent is constructed once and reused
    across all routes to avoid repeated AG2 initialisation overhead.
    """

    def __init__(self) -> None:
        self._analyzer = AnalyzerAgent()
        _log.info(json.dumps({"event": "pipeline_runner_initialized"}))

    def run(self) -> PipelineRunResult:
        """Execute the full pipeline and return a PipelineRunResult."""
        started_at = utcnow()
        errors: list[str] = []
        suppression_reasons: dict[str, int] = {}

        # ── Step 1: Scrape ───────────────────────────────────────────────────
        _log.info(json.dumps({"event": "pipeline_step", "step": "1_scrape"}))
        try:
            orchestrator = ScraperOrchestrator()
            scrape_result = orchestrator.run()
        except Exception as exc:
            _log.critical(
                json.dumps({
                    "event": "scrape_failed_critical",
                    "error": str(exc),
                })
            )
            finished_at = utcnow()
            # Early return on complete scrape failure
            empty_scrape = _make_empty_scrape_result(started_at, finished_at, str(exc))
            return PipelineRunResult(
                started_at=started_at,
                finished_at=finished_at,
                scrape_result=empty_scrape,
                retrain_triggered=False,
                retrain_result=None,
                routes_analysed=0,
                alerts_sent=0,
                alerts_suppressed=0,
                suppression_reasons={},
                errors=[f"Scrape failed: {exc}"],
                total_duration_seconds=(finished_at - started_at).total_seconds(),
            )

        _log.info(
            json.dumps({
                "event": "scrape_complete",
                "routes_succeeded": scrape_result.routes_succeeded,
                "fares_stored": scrape_result.total_fares_stored,
            })
        )

        # Collect routes that received new data
        routes_with_new_data: list[tuple[str, date]] = [
            (r.route, r.travel_date)
            for r in scrape_result.route_results
            if r.error is None and r.fares_stored > 0
        ]

        # ── Step 2: Retrain check ────────────────────────────────────────────
        _log.info(json.dumps({"event": "pipeline_step", "step": "2_retrain_check"}))
        retrain_triggered = False
        retrain_result: Optional[TrainingResult] = None

        try:
            if should_retrain():
                retrain_triggered = True
                _log.info(json.dumps({"event": "retrain_triggered"}))
                retrain_result = train()
        except Exception as exc:
            _log.error(
                json.dumps({
                    "event": "retrain_failed",
                    "error": str(exc),
                    "action": "continuing with existing model",
                })
            )
            errors.append(f"Retrain failed: {exc}")
            retrain_triggered = retrain_triggered  # keep as set if it was True

        # ── Steps 3–7: Per-route processing ──────────────────────────────────
        _log.info(
            json.dumps({
                "event": "pipeline_step",
                "step": "3-7_per_route",
                "routes": len(routes_with_new_data),
            })
        )

        routes_analysed = 0
        alerts_sent = 0
        alerts_suppressed = 0

        for route, travel_date in routes_with_new_data:
            try:
                sent, suppressed_reason = self._process_route(
                    route, travel_date
                )
                routes_analysed += 1
                if sent:
                    alerts_sent += 1
                else:
                    alerts_suppressed += 1
                    if suppressed_reason:
                        suppression_reasons[suppressed_reason] = (
                            suppression_reasons.get(suppressed_reason, 0) + 1
                        )
            except Exception as exc:
                error_msg = f"Route {route}/{travel_date} processing error: {exc}"
                _log.error(
                    json.dumps({
                        "event": "route_processing_error",
                        "route": route,
                        "travel_date": travel_date.isoformat(),
                        "error": str(exc),
                    })
                )
                errors.append(error_msg)
                # Continue — this route's error NEVER stops others

        finished_at = utcnow()
        duration = (finished_at - started_at).total_seconds()

        _log.info(
            json.dumps({
                "event": "pipeline_run_complete",
                "routes_analysed": routes_analysed,
                "alerts_sent": alerts_sent,
                "alerts_suppressed": alerts_suppressed,
                "errors": len(errors),
                "duration_seconds": round(duration, 1),
            })
        )

        return PipelineRunResult(
            started_at=started_at,
            finished_at=finished_at,
            scrape_result=scrape_result,
            retrain_triggered=retrain_triggered,
            retrain_result=retrain_result,
            routes_analysed=routes_analysed,
            alerts_sent=alerts_sent,
            alerts_suppressed=alerts_suppressed,
            suppression_reasons=suppression_reasons,
            errors=errors,
            total_duration_seconds=duration,
        )

    def _process_route(
        self, route: str, travel_date: date
    ) -> tuple[bool, Optional[str]]:
        """
        Run steps 3–7 for a single route+date pair.

        Returns (alert_sent: bool, suppression_reason: Optional[str]).
        suppression_reason is None if alert was sent or if we cannot determine reason.
        """
        # ── Step 3: Forecast ─────────────────────────────────────────────────
        _log.info(
            json.dumps({
                "event": "processing_route",
                "route": route,
                "travel_date": travel_date.isoformat(),
            })
        )

        try:
            # Get the most recent price for this route+date
            history = queries.get_price_history(route, travel_date, days_back=1)
            if not history:
                history = queries.get_price_history(route, travel_date, days_back=7)
            current_price = history[-1].price_inr if history else 0
            days_advance = (travel_date - date.today()).days

            forecast: ForecastScore = predict(
                route=route,
                travel_date=travel_date,
                current_price=current_price,
                days_advance=max(0, days_advance),
            )
        except Exception as exc:
            _log.error(
                json.dumps({
                    "event": "forecast_failed",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                    "error": str(exc),
                    "action": "using neutral forecast",
                })
            )
            from datetime import date as _date
            forecast = ForecastScore(
                route=route,
                travel_date=travel_date,
                lgbm_score=0.5,
                forecast_direction="flat",
                confidence=0.5,
                model_version="none",
                feature_values={},
            )
            current_price = 0

        # ── Step 3b: Store forecast in DB ────────────────────────────────────
        try:
            queries.store_ml_forecast(
                route=route,
                travel_date=travel_date,
                forecast_7d_price=None,
                forecast_direction=forecast.forecast_direction,
                lgbm_score=forecast.lgbm_score,
                confidence=forecast.confidence,
                model_version=forecast.model_version,
            )
        except Exception as exc:
            _log.error(
                json.dumps({
                    "event": "store_forecast_failed",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                    "error": str(exc),
                })
            )

        # ── Step 4: Analyse ──────────────────────────────────────────────────
        try:
            summary = build_price_summary(route, travel_date, current_price or None)
            if summary is None:
                _log.info(
                    json.dumps({
                        "event": "analysis_skipped",
                        "route": route,
                        "travel_date": travel_date.isoformat(),
                        "reason": "no price stats available yet",
                    })
                )
                analysis = _fallback_analysis(route, travel_date)
            else:
                analysis = self._analyzer.analyse(summary)
        except Exception as exc:
            _log.error(
                json.dumps({
                    "event": "analysis_failed",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                    "error": str(exc),
                    "action": "using fallback analysis",
                })
            )
            analysis = _fallback_analysis(route, travel_date)

        # ── Step 5: Gate evaluation ──────────────────────────────────────────
        try:
            if current_price <= 0:
                # Cannot evaluate without a valid price — suppress
                _log.info(
                    json.dumps({
                        "event": "alert_suppressed",
                        "route": route,
                        "travel_date": travel_date.isoformat(),
                        "reason": "no valid current price",
                    })
                )
                return False, "no_valid_price"

            decision: AlertDecision = evaluate_alert(
                route=route,
                travel_date=travel_date,
                current_price=current_price,
                analysis=analysis,
                forecast=forecast,
            )
        except Exception as exc:
            _log.error(
                json.dumps({
                    "event": "gate_evaluation_failed",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                    "error": str(exc),
                })
            )
            return False, f"gate_error: {exc}"

        if not decision.should_alert:
            # Determine which gate failed for suppression tracking
            if not decision.gate1_passed:
                reason = "gate1_statistical"
            elif not decision.gate2_passed:
                reason = "gate2_ml_score"
            else:
                reason = "gate3_cooldown"
            return False, reason

        # ── Step 6: Format and send alert ────────────────────────────────────
        try:
            message = format_alert_message(
                route=route,
                travel_date=travel_date,
                current_price=current_price,
                analysis=analysis,
                forecast=forecast,
                alert_decision=decision,
            )
        except Exception as exc:
            _log.error(
                json.dumps({
                    "event": "message_format_failed",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                    "error": str(exc),
                })
            )
            return False, "message_format_error"

        sent = send_telegram_alert(message, parse_mode="HTML")

        if sent:
            # ── Step 7: Log sent alert ───────────────────────────────────────
            try:
                alert_reason = (
                    f"Price ₹{current_price} ≤ P10 ₹{decision.p10_price}. "
                    f"ML score {decision.lgbm_score:.2f}. {analysis.key_insight}"
                )
                queries.log_alert_sent(
                    route=route,
                    travel_date=travel_date,
                    price_notified=current_price,
                    alert_reason=alert_reason[:500],  # cap reason length
                )
            except Exception as exc:
                _log.error(
                    json.dumps({
                        "event": "log_alert_sent_failed",
                        "route": route,
                        "travel_date": travel_date.isoformat(),
                        "error": str(exc),
                    })
                )
            return True, None
        else:
            _log.error(
                json.dumps({
                    "event": "telegram_send_failed_no_retry",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                    "note": "Not retrying to avoid duplicate alerts",
                })
            )
            return False, "telegram_send_failed"


# ─── PRIVATE HELPERS ─────────────────────────────────────────────────────────


def _fallback_analysis(route: str, travel_date: date) -> AnalysisReport:
    """Return a safe fallback AnalysisReport when the analyzer fails."""
    from agents.analyzer_agent import _fallback_report
    return _fallback_report(
        route, travel_date, "Analysis unavailable due to processing error."
    )


def _make_empty_scrape_result(
    started_at: datetime, finished_at: datetime, error: str
) -> ScrapeRunResult:
    """Build an empty ScrapeRunResult for the early-return error path."""
    return ScrapeRunResult(
        started_at=started_at,
        finished_at=finished_at,
        routes_attempted=0,
        routes_succeeded=0,
        routes_failed=0,
        total_fares_scraped=0,
        total_fares_stored=0,
        fallback_triggered_count=0,
        route_results=(),
        errors=(error,),
    )


# ─── CONVENIENCE FUNCTION ────────────────────────────────────────────────────


def run_pipeline() -> PipelineRunResult:
    """
    Convenience function. Instantiates PipelineRunner and calls run().
    This is the function called by FastAPI's POST /pipeline/run endpoint
    and the n8n webhook trigger.
    """
    runner = PipelineRunner()
    return runner.run()


# ─── FASTAPI ROUTER (mounted in Phase 4 by api/main.py) ─────────────────────

try:
    from fastapi import APIRouter
    router = APIRouter(prefix="/pipeline", tags=["pipeline"])

    @router.post("/run")
    async def trigger_pipeline_run():
        """Trigger a full scrape → forecast → analyse → alert pipeline run."""
        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(None, run_pipeline)
        return {
            "status": "completed",
            "alerts_sent": result.alerts_sent,
            "routes_analysed": result.routes_analysed,
            "duration_seconds": result.total_duration_seconds,
            "errors": result.errors,
        }

    @router.get("/status")
    async def pipeline_status():
        """Return rate limiter status and last run summary."""
        from agents.rate_limiter import RateLimiter
        rl = RateLimiter()
        return rl.get_status()

except ImportError:
    router = None  # FastAPI not installed yet — Phase 4 will add it
