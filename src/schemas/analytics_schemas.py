"""Esquemes Pydantic per a les consultes i respostes estructurades de l'AnalyticsAgent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class AnalyticsMetric(BaseModel):
    """Mètrica quantitativa o indicador clau de rendiment (KPI)."""

    name: str = Field(description="Nom identificador de la mètrica")
    value: float = Field(description="Valor numèric calculat o agregat")
    unit: Optional[str] = Field(default=None, description="Unitat de mesura (p. ex. '%', 'segons', 'USD')")
    trend: Optional[Literal["up", "down", "stable"]] = Field(
        default=None,
        description="Tendència observada respecte a períodes anteriors",
    )


class AnalyticsInsight(BaseModel):
    """Conclusió, patró o observació clau derivada de l'anàlisi de dades."""

    title: str = Field(description="Títol breu i descriptiu de l'observació")
    description: str = Field(description="Descripció detallada del patró trobat o de la troballa")
    severity: Literal["info", "warning", "critical", "positive"] = Field(
        default="info",
        description="Nivell de rellevància o severitat de la conclusió",
    )
    actionable_recommendation: Optional[str] = Field(
        default=None,
        description="Recomanació operativa o acció de millora suggerida",
    )


class AnalyticsQuery(BaseModel):
    """Model de sol·licitud o consulta analítica d'entrada."""

    query: str = Field(description="Pregunta o objectiu analític formulat en llenguatge natural")
    data_payload: dict[str, Any] | list[Any] = Field(
        description="Dades estructurades a analitzar (diccionari de registres o llista de dades)"
    )
    context: Optional[str] = Field(default=None, description="Context de negoci o paràmetres addicionals")

    @field_validator("query")
    @classmethod
    def validate_non_empty_query(cls, value: str) -> str:
        """Comprova que la consulta no sigui buida ni contingui només espais.

        Args:
            value: Text de la consulta.

        Returns:
            str: Text netejat.

        Raises:
            ValueError: Si la consulta està buida.
        """
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("La consulta analítica no pot estar buida.")
        return cleaned

    @field_validator("data_payload")
    @classmethod
    def validate_non_empty_data(cls, value: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
        """Comprova que el conjunt de dades tingui elements analitzables.

        Args:
            value: Dades en format diccionari o llista.

        Returns:
            dict[str, Any] | list[Any]: Les mateixes dades validades.

        Raises:
            ValueError: Si el contenidor de dades és buit.
        """
        if not value:
            raise ValueError("El conjunt de dades a analitzar no pot estar buit.")
        return value


class AnalyticsResponse(BaseModel):
    """Resposta estructurada emesa per l'Agent Analític d'IA."""

    status: Literal["success", "partial", "error"] = Field(
        default="success",
        description="Estat d'execució de la consulta analítica",
    )
    summary: str = Field(description="Resum executiu d'alt nivell de l'anàlisi")
    insights: list[AnalyticsInsight] = Field(
        default_factory=list,
        description="Llista d'observacions clau i conclusions trobades",
    )
    metrics: list[AnalyticsMetric] = Field(
        default_factory=list,
        description="Mètriques agregades rellevants calculades durant l'anàlisi",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Marca temporal ISO de l'execució",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadades auxiliars sobre l'execució i l'anàlisi realitzada",
    )
