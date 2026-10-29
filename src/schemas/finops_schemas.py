"""Esquemes Pydantic per a la gestió de telemetria de consum de tokens i costos FinOps."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TokenUsage(BaseModel):
    """Model de dades per al registre de consum de tokens en crides a models LLM."""

    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Nombre de tokens consumits en el prompt o entrada de la petició",
    )
    completion_tokens: int = Field(
        default=0,
        ge=0,
        description="Nombre de tokens generats en la resposta o sortida del model",
    )
    cached_tokens: int = Field(
        default=0,
        ge=0,
        description="Nombre de tokens servits des de memòria cau de context",
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Suma total de tokens consumits en la transacció",
    )

    @model_validator(mode="after")
    def compute_or_validate_total(self) -> TokenUsage:
        """Assegura la coherència de cached_tokens i valida o calcula total_tokens.

        Garanteix que cached_tokens no superi prompt_tokens i que, en cas d'introduir
        total_tokens manualment, el seu valor sigui major o igual a la suma de
        prompt_tokens i completion_tokens.

        Returns:
            TokenUsage: Instància validada amb el còmput de tokens.

        Raises:
            ValueError: Si cached_tokens és estrictament superior a prompt_tokens o
                si total_tokens és inferior a la suma de prompt_tokens i completion_tokens.
        """
        if self.cached_tokens > self.prompt_tokens:
            raise ValueError(
                f"cached_tokens ({self.cached_tokens}) no pot ser superior a "
                f"prompt_tokens ({self.prompt_tokens})."
            )
        calculated = self.prompt_tokens + self.completion_tokens
        if self.total_tokens == 0 and calculated > 0:
            object.__setattr__(self, "total_tokens", calculated)
        elif self.total_tokens < calculated:
            raise ValueError(
                f"total_tokens ({self.total_tokens}) no pot ser inferior a la "
                f"suma de prompt_tokens i completion_tokens ({calculated})."
            )
        return self


class PricingTier(BaseModel):
    """Tarifa de preus per model de LLM expressada en dòlars americans (USD) per 1.000 tokens."""

    model_name: str = Field(description="Identificador canònic del model (ex: 'gemini-2.5-flash')")
    provider: str = Field(default="google", description="Proveïdor del model (ex: 'google', 'openai')")
    input_cost_per_k: float = Field(
        ge=0.0,
        description="Cost en USD per cada 1.000 tokens d'entrada (prompt)",
    )
    output_cost_per_k: float = Field(
        ge=0.0,
        description="Cost en USD per cada 1.000 tokens de sortida (completion)",
    )
    cached_cost_per_k: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost en USD per cada 1.000 tokens llegits de la memòria cau",
    )

    @field_validator("model_name", "provider")
    @classmethod
    def check_non_empty_strings(cls, v: str) -> str:
        """Valida que els camps identificadors no siguin cadenes buides."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("El camp identificador no pot estar buit.")
        return cleaned


class CostBreakdown(BaseModel):
    """Desglossament detallat del cost econòmic estimat d'una transacció de LLM."""

    model_name: str = Field(description="Model utilitzat en el càlcul")
    input_cost: float = Field(ge=0.0, description="Cost atribuïble als tokens d'entrada")
    output_cost: float = Field(ge=0.0, description="Cost atribuïble als tokens generats")
    cached_cost: float = Field(default=0.0, ge=0.0, description="Cost atribuïble a tokens en cau")
    total_cost: float = Field(ge=0.0, description="Cost econòmic total de la interacció")
    currency: str = Field(default="USD", description="Moneda del càlcul financer")
    details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Metadades addicionals o ràtios de consum de la transacció",
    )


class CallMetricRecord(BaseModel):
    """Registre individual d'una invocació de LLM amb telemetria de temps i rendiment."""

    model_name: str = Field(description="Identificador del model executat")
    duration_seconds: float = Field(ge=0.0, description="Durada de la petició en segons")
    usage: TokenUsage = Field(description="Mètriques de tokens consumits")
    cost: CostBreakdown = Field(description="Cost FinOps calculat per a la crida")
    tokens_per_second: float = Field(
        default=0.0,
        ge=0.0,
        description="Ràtio de velocitat expressada en tokens totals per segon (TPS)",
    )
    completion_tps: float = Field(
        default=0.0,
        ge=0.0,
        description="Ràtio de generació expressada en completion tokens per segon",
    )


class SessionSummary(BaseModel):
    """Resum agregat de telemetria i costos FinOps per a una sessió de treball."""

    total_calls: int = Field(ge=0, description="Nombre total de crides registrades")
    total_duration_seconds: float = Field(ge=0.0, description="Durada acumulada de totes les crides")
    average_latency_seconds: float = Field(ge=0.0, description="Latència mitjana per crida")
    total_tokens: int = Field(ge=0, description="Suma total de tokens utilitzats")
    total_prompt_tokens: int = Field(ge=0, description="Suma de tokens d'entrada")
    total_completion_tokens: int = Field(ge=0, description="Suma de tokens de resposta")
    total_cached_tokens: int = Field(ge=0, description="Suma de tokens servits des de memòria cau")
    total_cost_usd: float = Field(ge=0.0, description="Cost econòmic global acumulat en USD")
    global_tps: float = Field(ge=0.0, description="Velocitat global en tokens totals per segon")
    by_model: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Desglossament agregat de crides, tokens i costos per model",
    )
