"""Servei de telemetria i monitoratge de rendiment, latència i eficiència d'execució d'agents."""

from __future__ import annotations

import argparse
import json
import time
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

from src.schemas.finops_schemas import (
    CallMetricRecord,
    CostBreakdown,
    SessionSummary,
    TokenUsage,
)
from src.services.finops_service import CostCalculator, FinOpsPricingCatalog
from src.utils.logger import AgentLogger, StructuredAgentAdapter

DEFAULT_MAX_RECORDS_LIMIT: int = 10000
DEFAULT_METRICS_FILE: Path = Path("logs/metrics.jsonl")


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

    def __init__(
        self,
        calculator: Optional[CostCalculator] = None,
        max_records: Optional[int] = DEFAULT_MAX_RECORDS_LIMIT,
    ) -> None:
        """Inicialitza el gestor de mètriques de telemetria amb gestió de buffer circular.

        Args:
            calculator: Instància opcional del calculador de costos FinOps.
            max_records: Nombre màxim de registres retinguts a memòria (buffer circular).
                Per defecte s'aplica `DEFAULT_MAX_RECORDS_LIMIT` (10000) per prevenir
                riscos d'exhauriment de memòria (OWASP A04 - DoS/OOM). Es pot indicar
                un altre enter positiu o `None` per permetre un historial sense límit.

        Raises:
            ValueError: Si max_records és menor o igual a zero.
        """
        if max_records is not None and max_records <= 0:
            raise ValueError("El paràmetre max_records ha de ser un enter estrictament positiu.")

        self.calculator: CostCalculator = calculator or CostCalculator()
        self._max_records: Optional[int] = max_records
        self._records: deque[CallMetricRecord] = deque(maxlen=max_records)
        base_logger = AgentLogger.get_logger("MetricsTracker")
        self.logger = StructuredAgentAdapter(base_logger, "MetricsTracker")

    @property
    def max_records(self) -> Optional[int]:
        """Obté el límit màxim de registres històrics configurat al buffer circular.

        Returns:
            Optional[int]: Nombre màxim de registres o None si no hi ha límit.
        """
        return self._max_records

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

    def purge_oldest(self, count: int) -> int:
        """Purga manualment els registres més antics de memòria per alliberar espai.

        Args:
            count: Nombre de registres a eliminar començant pel més antic.

        Returns:
            int: Nombre real de registres expulsats de memòria.

        Raises:
            ValueError: Si count és menor o igual a zero.
        """
        if count <= 0:
            raise ValueError("El nombre de registres a purgar ha de ser un enter estrictament positiu.")

        to_remove = min(count, len(self._records))
        for _ in range(to_remove):
            self._records.popleft()

        self.logger.info(f"S'han purgat {to_remove} registres antics de memòria.")
        return to_remove

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
        global_completion_tps = self.calculate_tps(total_completion, total_duration)

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
            global_completion_tps=global_completion_tps,
            by_model=by_model,
        )

    def append_record_to_file(
        self,
        record: CallMetricRecord,
        file_path: Path | str = DEFAULT_METRICS_FILE,
    ) -> None:
        """Persisteix un registre individual de mètriques al fitxer històric JSONL.

        Args:
            record: Registre de crida amb latència, tokens i cost FinOps.
            file_path: Ruta al fitxer JSONL de destinació (per defecte `logs/metrics.jsonl`).
        """
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(record.model_dump_json() + "\n")

    @classmethod
    def load_from_file(
        cls,
        file_path: Path | str = DEFAULT_METRICS_FILE,
        model_filter: Optional[str] = None,
        max_records: Optional[int] = DEFAULT_MAX_RECORDS_LIMIT,
        calculator: Optional[CostCalculator] = None,
    ) -> MetricsTracker:
        """Reconstrueix una instància de MetricsTracker carregant l'històric JSONL de disc.

        Args:
            file_path: Ruta al fitxer JSONL amb els registres històrics.
            model_filter: Filtre opcional per nom de model (insensible a majúscules).
            max_records: Límit màxim de registres a retenir al buffer circular.
            calculator: Calculador de costos FinOps opcional.

        Returns:
            MetricsTracker: Instància carregada amb els registres històrics filtrats.
        """
        tracker = cls(calculator=calculator, max_records=max_records)
        target = Path(file_path)
        if not target.exists():
            return tracker

        normalized_filter = model_filter.strip().lower() if model_filter else None
        for raw_line in target.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = CallMetricRecord.model_validate_json(line)
            except Exception:
                continue
            if normalized_filter and normalized_filter not in record.model_name.lower():
                continue
            tracker._records.append(record)

        return tracker

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

    def format_report(self, last_n: int = 10) -> str:
        """Genera un informe visual estructurat en format taula per a terminal.

        Args:
            last_n: Nombre màxim de darreres crides individuals a mostrar (0 per ometre).

        Returns:
            str: Informe formatat amb el resum global, desglossament per model i crides recents.
        """
        summary = self.get_summary()
        sep = "=" * 86
        sub_sep = "-" * 86
        lines: list[str] = [
            sep,
            "📊 TELEMETRIA DE TOKENS, COSTOS (FINOPS) I MÈTRIQUES D'EFICIÈNCIA",
            sep,
        ]

        if summary.total_calls == 0:
            lines.extend([
                "ℹ️  No s'ha trobat cap registre de telemetria.",
                "   Les mètriques es desaran automàticament a 'logs/metrics.jsonl' durant",
                "   les execucions dels agents (AnalystAgent, DeveloperAgent, CodeReviewAgent).",
                sep,
            ])
            return "\n".join(lines)

        lines.extend([
            "🔹 RESUM GLOBAL ACUMULAT:",
            f"   • Crides totals al LLM      : {summary.total_calls}",
            f"   • Durada total acumulada    : {summary.total_duration_seconds:.3f} s",
            f"   • Latència mitjana / crida  : {summary.average_latency_seconds:.3f} s",
            f"   • Velocitat global (TPS)    : {summary.global_tps:.2f} tok/s "
            f"(Generació: {summary.global_completion_tps:.2f} tok/s)",
            f"   • Tokens consumits          : {summary.total_tokens:,} totals "
            f"(Prompt: {summary.total_prompt_tokens:,} | "
            f"Cached: {summary.total_cached_tokens:,} | "
            f"Completion: {summary.total_completion_tokens:,})",
            f"   • Cost FinOps total (USD)   : ${summary.total_cost_usd:.6f} USD",
            "",
            "🔹 DESGLOSSAMENT PER MODEL LLM:",
            sub_sep,
            f"{'Model':<24} | {'Crides':>6} | {'Prompt':>9} | {'Completion':>10} | "
            f"{'Total Tok':>10} | {'TPS':>8} | {'Cost (USD)':>11}",
            sub_sep,
        ])

        for model_name, m_stats in sorted(summary.by_model.items()):
            lines.append(
                f"{model_name:<24} | "
                f"{int(m_stats['calls']):>6} | "
                f"{int(m_stats['prompt_tokens']):>9,} | "
                f"{int(m_stats['completion_tokens']):>10,} | "
                f"{int(m_stats['total_tokens']):>10,} | "
                f"{float(m_stats['tps']):>8.2f} | "
                f"${float(m_stats['cost_usd']):>10.6f}"
            )
        lines.append(sub_sep)

        if last_n > 0 and self._records:
            recent = list(self._records)[-last_n:]
            lines.extend([
                "",
                f"🔹 DARRERES {len(recent)} CRIDES REGISTRADES:",
                sub_sep,
                f"{'Timestamp (UTC)':<20} | {'Model':<22} | {'Latència':>8} | "
                f"{'Tokens (In/Out/Tot)':>21} | {'TPS':>8} | {'Cost (USD)':>11}",
                sub_sep,
            ])
            for rec in recent:
                ts_short = rec.timestamp[:19].replace("T", " ")
                tok_summary = (
                    f"{rec.usage.prompt_tokens}/{rec.usage.completion_tokens}/"
                    f"{rec.usage.total_tokens}"
                )
                lines.append(
                    f"{ts_short:<20} | "
                    f"{rec.model_name:<22} | "
                    f"{rec.duration_seconds:>7.2f}s | "
                    f"{tok_summary:>21} | "
                    f"{rec.tokens_per_second:>8.2f} | "
                    f"${rec.cost.total_cost:>10.6f}"
                )
            lines.append(sub_sep)

        lines.append(sep)
        return "\n".join(lines)


def format_pricing_catalog_table(catalog: Optional[FinOpsPricingCatalog] = None) -> str:
    """Formata el catàleg de tarifes FinOps en una taula llegible per terminal.

    Args:
        catalog: Catàleg de preus opcional; si és None, s'utilitza el catàleg per defecte.

    Returns:
        str: Taula formatada amb els costos per cada 1.000 tokens de cada model registrat.
    """
    active_catalog = catalog or FinOpsPricingCatalog()
    tiers = active_catalog.list_tiers()
    sep = "=" * 86
    sub_sep = "-" * 86
    lines: list[str] = [
        sep,
        "💰 CATÀLEG DE TARIFES FINOPS (USD per 1.000 tokens)",
        sep,
        f"{'Model':<24} | {'Proveïdor':<10} | {'Input / 1k':>14} | "
        f"{'Cached / 1k':>14} | {'Output / 1k':>14}",
        sub_sep,
    ]
    for tier in tiers:
        lines.append(
            f"{tier.model_name:<24} | "
            f"{tier.provider:<10} | "
            f"${tier.input_cost_per_k:>13.8f} | "
            f"${tier.cached_cost_per_k:>13.8f} | "
            f"${tier.output_cost_per_k:>13.8f}"
        )
    lines.append(sep)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Punt d'entrada CLI per consultar i gestionar les mètriques FinOps i de telemetria.

    Args:
        argv: Llista d'arguments de línia d'ordres (si és None, llegeix `sys.argv[1:]`).

    Returns:
        int: Codi de sortida del procés (`0` si té èxit, `1` en cas d'error).
    """
    parser = argparse.ArgumentParser(
        prog="ai-metrics",
        description="Visualitzador i gestor de telemetria de tokens, costos FinOps i eficiència.",
    )
    parser.add_argument(
        "-f",
        "--file",
        default=str(DEFAULT_METRICS_FILE),
        help=f"Ruta al fitxer JSONL de mètriques (per defecte: {DEFAULT_METRICS_FILE}).",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Exporta l'informe complet de mètriques en format JSON estructurat.",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=None,
        help="Filtra les mètriques per nom de model LLM (ex: gemini-3.8-flash).",
    )
    parser.add_argument(
        "-n",
        "--last",
        type=int,
        default=10,
        help="Nombre de darreres crides individuals a mostrar a l'informe (per defecte: 10).",
    )
    parser.add_argument(
        "-c",
        "--catalog",
        action="store_true",
        help="Mostra la taula del catàleg de tarifes FinOps per model i surt.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Esborra els registres acumulats al fitxer històric de mètriques.",
    )
    args = parser.parse_args(argv)

    if args.catalog:
        print(format_pricing_catalog_table())
        return 0

    metrics_path = Path(args.file)
    if args.reset:
        if metrics_path.exists():
            metrics_path.unlink()
        print(f"✅ Històric de mètriques reiniciat: {metrics_path}")
        return 0

    tracker = MetricsTracker.load_from_file(
        file_path=metrics_path,
        model_filter=args.model,
    )
    if args.json:
        print(tracker.export_json())
    else:
        print(tracker.format_report(last_n=max(0, args.last)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
