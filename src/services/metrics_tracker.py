"""Servei de telemetria i monitoratge de rendiment, latència i eficiència d'execució d'agents."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from src.schemas.finops_schemas import (
    CallMetricRecord,
    CostBreakdown,
    SessionSummary,
    TokenUsage,
)
from src.services.finops_service import CostCalculator
from src.utils.logger import AgentLogger, StructuredAgentAdapter


class CallTrackingContext:
    """Context d'una crida individual per registrar l'ús de tokens i mesurar la durada."""

    def __init__(self, model_name: str, initial_usage: Optional[TokenUsage] = None) -> None:
        """Inicialitza el context de mesura de la crida.

        Args:
            model_name: Identificador del model LLM que s'invoca.
            initial_usage: Ús inicial de tokens si ja és conegut abans d'iniciar la crida.
        """
        self.model_name: str = model_name
        self.usage: TokenUsage = initial_usage or TokenUsage()
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration_seconds: float = 0.0

    def set_usage(
        self,
        usage: Optional[TokenUsage] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> None:
        """Actualitza els tokens consumits durant la crida.

        Args:
            usage: Instància directa de TokenUsage.
            prompt_tokens: Nombre de tokens d'entrada si no es passa `usage`.
            completion_tokens: Nombre de tokens generats si no es passa `usage`.
            cached_tokens: Nombre de tokens en cau si no es passa `usage`.
        """
        if usage is not None:
            self.usage = usage
        else:
            self.usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
            )


class MetricsTracker:
    """Seguiment de mètriques de sessió, càlcul de latències, TPS i integració FinOps."""

    def __init__(self, calculator: Optional[CostCalculator] = None) -> None:
        """Inicialitza el gestor de mètriques de telemetria.

        Args:
            calculator: Instància opcional del calculador de costos FinOps.
        """
        self.calculator: CostCalculator = calculator or CostCalculator()
        self._records: list[CallMetricRecord] = []
        base_logger = AgentLogger.get_logger("MetricsTracker")
        self.logger = StructuredAgentAdapter(base_logger, "MetricsTracker")

    @property
    def records(self) -> list[CallMetricRecord]:
        """Retorna la llista immutable de registres de mètriques de la sessió actual.

        Returns:
            list[CallMetricRecord]: Còpia dels registres emmagatzemats.
        """
        return list(self._records)

    def reset(self) -> None:
        """Reinicia totes les mètriques acumulades a la sessió actual."""
        self._records.clear()
        self.logger.info("Mètriques de sessió reiniciades.")

    @staticmethod
    def calculate_tps(tokens: int, duration_seconds: float) -> float:
        """Calcula la ràtio de tokens per segon protegint contra divisions per zero.

        Args:
            tokens: Nombre de tokens comptabilitzats.
            duration_seconds: Temps d'execució en segons.

        Returns:
            float: Tokens per segon arrodonits a 2 decimals (0.0 si la durada és nul·la).
        """
        if duration_seconds <= 0.0 or tokens <= 0:
            return 0.0
        return round(float(tokens) / duration_seconds, 2)

    def record_call(
        self,
        model_name: str,
        usage: TokenUsage,
        duration_seconds: float,
    ) -> CallMetricRecord:
        """Registra explícitament una operació i calcula el seu cost i eficiència.

        Args:
            model_name: Nom del model de LLM emprat.
            usage: Dades estructurades del consum de tokens.
            duration_seconds: Temps emprat en l'execució en segons.

        Returns:
            CallMetricRecord: Registre creat amb les mètriques i costos associats.
        """
        safe_duration = max(0.0, float(duration_seconds))
        cost = self.calculator.calculate_cost(model_name=model_name, usage=usage)
        tps = self.calculate_tps(usage.total_tokens, safe_duration)
        completion_tps = self.calculate_tps(usage.completion_tokens, safe_duration)

        record = CallMetricRecord(
            model_name=model_name,
            duration_seconds=round(safe_duration, 4),
            usage=usage,
            cost=cost,
            tokens_per_second=tps,
            completion_tps=completion_tps,
        )
        self._records.append(record)
        self.logger.info(
            f"Crida registrada: {model_name} | {usage.total_tokens} tokens | "
            f"{safe_duration:.3f}s | {tps} TPS | {cost.total_cost} USD"
        )
        return record

    @contextmanager
    def track_call(
        self,
        model_name: str,
        usage: Optional[TokenUsage] = None,
    ) -> Iterator[CallTrackingContext]:
        """Context manager per mesurar de forma transparent la latència d'una crida.

        Args:
            model_name: Nom del model que s'executarà dins del context.
            usage: Consum de tokens opcional si es coneix per endavant.

        Yields:
            CallTrackingContext: Objecte de context per modificar l'ús de tokens.
        """
        context = CallTrackingContext(model_name=model_name, initial_usage=usage)
        context.start_time = time.perf_counter()
        try:
            yield context
        finally:
            context.end_time = time.perf_counter()
            context.duration_seconds = max(0.0, context.end_time - context.start_time)
            self.record_call(
                model_name=context.model_name,
                usage=context.usage,
                duration_seconds=context.duration_seconds,
            )

    def get_summary(self) -> SessionSummary:
        """Calcula el resum complet agregat de totes les crides registrades a la sessió.

        Returns:
            SessionSummary: Resum amb totals de tokens, costos, latència mitjana i TPS global.
        """
        total_calls = len(self._records)
        if total_calls == 0:
            return SessionSummary(
                total_calls=0,
                total_duration_seconds=0.0,
                average_latency_seconds=0.0,
                total_tokens=0,
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_cached_tokens=0,
                total_cost_usd=0.0,
                global_tps=0.0,
                by_model={},
            )

        total_duration = sum(r.duration_seconds for r in self._records)
        total_tokens = sum(r.usage.total_tokens for r in self._records)
        total_prompt = sum(r.usage.prompt_tokens for r in self._records)
        total_completion = sum(r.usage.completion_tokens for r in self._records)
        total_cached = sum(r.usage.cached_tokens for r in self._records)
        total_cost = sum(r.cost.total_cost for r in self._records)
        avg_latency = total_duration / total_calls if total_calls > 0 else 0.0
        global_tps = self.calculate_tps(total_tokens, total_duration)

        by_model: dict[str, dict[str, Any]] = {}
        for r in self._records:
            m = r.model_name
            if m not in by_model:
                by_model[m] = {
                    "calls": 0,
                    "duration_seconds": 0.0,
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cached_tokens": 0,
                    "cost_usd": 0.0,
                }
            by_model[m]["calls"] += 1
            by_model[m]["duration_seconds"] = round(
                by_model[m]["duration_seconds"] + r.duration_seconds, 4
            )
            by_model[m]["total_tokens"] += r.usage.total_tokens
            by_model[m]["prompt_tokens"] += r.usage.prompt_tokens
            by_model[m]["completion_tokens"] += r.usage.completion_tokens
            by_model[m]["cached_tokens"] += r.usage.cached_tokens
            by_model[m]["cost_usd"] = round(by_model[m]["cost_usd"] + r.cost.total_cost, 6)

        for m_data in by_model.values():
            m_data["tps"] = self.calculate_tps(
                m_data["total_tokens"], m_data["duration_seconds"]
            )

        return SessionSummary(
            total_calls=total_calls,
            total_duration_seconds=round(total_duration, 4),
            average_latency_seconds=round(avg_latency, 4),
            total_tokens=total_tokens,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_cached_tokens=total_cached,
            total_cost_usd=round(total_cost, 6),
            global_tps=global_tps,
            by_model=by_model,
        )

    def export_dict(self) -> dict[str, Any]:
        """Exporta el resum de mètriques i el detall de crides com a diccionari natiu.

        Returns:
            dict[str, Any]: Diccionari amb el resum agregat i els registres individuals.
        """
        summary = self.get_summary()
        return {
            "summary": summary.model_dump(),
            "calls": [r.model_dump() for r in self._records],
        }

    def export_json(self, indent: int = 2) -> str:
        """Exporta les estadístiques de telemetria en una cadena JSON formatada.

        Args:
            indent: Nombre d'espais per a la indentació del JSON (per defecte: 2).

        Returns:
            str: Text JSON vàlid amb les mètriques i costos de la sessió.
        """
        return json.dumps(self.export_dict(), indent=indent, ensure_ascii=False)
