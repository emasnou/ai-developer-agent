"""Servei de catàleg de preus i motor de càlcul de costos FinOps per a models de LLM."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml

from src.schemas.finops_schemas import CostBreakdown, PricingTier, TokenUsage
from src.utils.logger import AgentLogger, StructuredAgentAdapter

DEFAULT_PRICING_CATALOG: dict[str, dict[str, Any]] = {
    "gemini-2.5-flash": {
        "provider": "google",
        "input_cost_per_k": 0.000075,
        "output_cost_per_k": 0.0003,
        "cached_cost_per_k": 0.00001875,
    },
    "gemini-2.5-flash-lite": {
        "provider": "google",
        "input_cost_per_k": 0.0000375,
        "output_cost_per_k": 0.00015,
        "cached_cost_per_k": 0.000009375,
    },
    "gemini-1.5-pro": {
        "provider": "google",
        "input_cost_per_k": 0.00125,
        "output_cost_per_k": 0.005,
        "cached_cost_per_k": 0.0003125,
    },
    "gpt-4o": {
        "provider": "openai",
        "input_cost_per_k": 0.005,
        "output_cost_per_k": 0.015,
        "cached_cost_per_k": 0.0025,
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "input_cost_per_k": 0.00015,
        "output_cost_per_k": 0.0006,
        "cached_cost_per_k": 0.000075,
    },
}


class ModelPricingNotFoundError(Exception):
    """Excepció llançada quan s'intenta calcular el cost d'un model no registrat al catàleg."""

    def __init__(self, model_name: str) -> None:
        """Inicialitza l'error indicant el model no suportat.

        Args:
            model_name: Nom del model no trobat al catàleg.
        """
        super().__init__(f"No s'ha trobat cap tarifa de preus per al model '{model_name}'.")
        self.model_name = model_name


class FinOpsPricingCatalog:
    """Catàleg configurable de tarifes de consum de tokens per model i proveïdor de LLM."""

    def __init__(self, initial_catalog: Optional[dict[str, PricingTier]] = None) -> None:
        """Inicialitza el catàleg de tarifes FinOps.

        Args:
            initial_catalog: Diccionari opcional de tarifes indexades per nom de model.
        """
        self._catalog: dict[str, PricingTier] = {}
        if initial_catalog is not None:
            for model_name, tier in initial_catalog.items():
                self.register_tier(tier)
        else:
            self.load_defaults()

    def load_defaults(self) -> None:
        """Carrega les tarifes de preus estàndard per defecte del sistema."""
        for model_name, values in DEFAULT_PRICING_CATALOG.items():
            self.register_tier(
                PricingTier(
                    model_name=model_name,
                    provider=values["provider"],
                    input_cost_per_k=values["input_cost_per_k"],
                    output_cost_per_k=values["output_cost_per_k"],
                    cached_cost_per_k=values["cached_cost_per_k"],
                )
            )

    def register_tier(self, tier: PricingTier) -> None:
        """Afegeix o actualitza una tarifa de preus per a un model determinat.

        Args:
            tier: Instància de PricingTier a registrar.
        """
        self._catalog[tier.model_name.strip().lower()] = tier

    def get_tier(self, model_name: str) -> PricingTier:
        """Recupera la tarifa associada al model indicat.

        Args:
            model_name: Identificador del model de LLM.

        Returns:
            PricingTier: Tarifa de preus registrada.

        Raises:
            ModelPricingNotFoundError: Si el model no està present al catàleg.
        """
        normalized = model_name.strip().lower()
        tier = self._catalog.get(normalized)
        if tier is None:
            raise ModelPricingNotFoundError(model_name)
        return tier

    def has_tier(self, model_name: str) -> bool:
        """Comprova si el model té una tarifa registrada al catàleg.

        Args:
            model_name: Identificador del model.

        Returns:
            bool: True si el model està registrat, False altrament.
        """
        return model_name.strip().lower() in self._catalog

    @classmethod
    def from_file(cls, file_path: Path | str) -> FinOpsPricingCatalog:
        """Construeix un catàleg de preus a partir d'un fitxer JSON o YAML.

        Args:
            file_path: Ruta del fitxer de configuració de preus.

        Returns:
            FinOpsPricingCatalog: Nova instància amb les tarifes carregades.

        Raises:
            ValueError: Si el format del fitxer no és suportat o té sintaxi errònia.
            FileNotFoundError: Si el fitxer no existeix a disc.
        """
        target_path = Path(file_path)
        if not target_path.exists():
            raise FileNotFoundError(f"No s'ha trobat el fitxer de tarifes: '{target_path}'")

        content = target_path.read_text(encoding="utf-8")
        suffix = target_path.suffix.lower()

        if suffix == ".json":
            raw_data = json.loads(content)
        elif suffix in (".yml", ".yaml"):
            raw_data = yaml.safe_load(content)
        else:
            raise ValueError(f"Format de fitxer de tarifes no suportat: '{suffix}'")

        if not isinstance(raw_data, (dict, list)):
            raise ValueError("El fitxer de tarifes ha de contenir una llista o diccionari d'elements.")

        catalog = cls(initial_catalog={})
        items = raw_data.values() if isinstance(raw_data, dict) else raw_data
        for item in items:
            if isinstance(item, dict):
                tier = PricingTier(**item)
                catalog.register_tier(tier)

        return catalog


class CostCalculator:
    """Motor de càlcul econòmic FinOps basat en consum de tokens i tarifes configurades."""

    def __init__(self, catalog: Optional[FinOpsPricingCatalog] = None) -> None:
        """Inicialitza el calculador de costos FinOps.

        Args:
            catalog: Catàleg de preus opcional; si és None, s'utilitza un catàleg per defecte.
        """
        self.catalog: FinOpsPricingCatalog = catalog or FinOpsPricingCatalog()
        base_logger = AgentLogger.get_logger("CostCalculator")
        self.logger = StructuredAgentAdapter(base_logger, "CostCalculator")

    def calculate_cost(
        self,
        model_name: str,
        usage: TokenUsage,
        round_digits: int = 10,
    ) -> CostBreakdown:
        """Calcula el cost econòmic exacte associat a una interacció amb un LLM.

        Aplica el càlcul matemàtic:
        - cost_entrada = (prompt_tokens - cached_tokens) * (input_cost_per_k / 1000)
        - cost_cau = cached_tokens * (cached_cost_per_k / 1000)
        - cost_sortida = completion_tokens * (output_cost_per_k / 1000)
        - cost_total = cost_entrada + cost_cau + cost_sortida

        Args:
            model_name: Nom o identificador del model utilitzat.
            usage: Dades estructurades del consum de tokens.
            round_digits: Nombre de decimals per a l'arrodoniment monetari (per defecte 10).

        Returns:
            CostBreakdown: Detall econòmic complet de la transacció.

        Raises:
            ModelPricingNotFoundError: Si el model no està present al catàleg.
        """
        tier = self.catalog.get_tier(model_name)

        # Deduïm els tokens en cau del prompt per no cobrar-los dues vegades
        uncached_prompt_tokens = max(0, usage.prompt_tokens - usage.cached_tokens)
        input_cost = (uncached_prompt_tokens / 1000.0) * tier.input_cost_per_k
        cached_cost = (usage.cached_tokens / 1000.0) * tier.cached_cost_per_k
        output_cost = (usage.completion_tokens / 1000.0) * tier.output_cost_per_k
        total_cost = input_cost + cached_cost + output_cost

        breakdown = CostBreakdown(
            model_name=tier.model_name,
            input_cost=round(input_cost, round_digits),
            output_cost=round(output_cost, round_digits),
            cached_cost=round(cached_cost, round_digits),
            total_cost=round(total_cost, round_digits),
            currency="USD",
            details={
                "provider": tier.provider,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "cached_tokens": usage.cached_tokens,
                "total_tokens": usage.total_tokens,
            },
        )

        self.logger.info(
            f"Cost calculat per a '{tier.model_name}': {breakdown.total_cost} USD "
            f"({usage.total_tokens} tokens total)"
        )
        return breakdown

    def calculate_batch_cost(
        self,
        usages: list[tuple[str, TokenUsage]],
        round_digits: int = 10,
    ) -> list[CostBreakdown]:
        """Processa un lot de consums de tokens i retorna els costos associats de forma seqüencial.

        Args:
            usages: Llista de tuples (model_name, usage) a calcular.
            round_digits: Precisió d'arrodoniment decimal (per defecte 10).

        Returns:
            list[CostBreakdown]: Llista de desglossaments econòmics corresponents.
        """
        results: list[CostBreakdown] = []
        for model_name, usage in usages:
            breakdown = self.calculate_cost(model_name=model_name, usage=usage, round_digits=round_digits)
            results.append(breakdown)
        return results
