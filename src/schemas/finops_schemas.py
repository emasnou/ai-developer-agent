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
        """Assegura que total_tokens reflecteixi la suma dels tokens si no s'ha especificat."""
        calculated = self.prompt_tokens + self.completion_tokens
        if self.total_tokens == 0 and calculated > 0:
            object.__setattr__(self, "total_tokens", calculated)
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
