"""Agent Analític d'IA modular per al processament, inspecció i extracció d'insights de dades."""

from __future__ import annotations

import json
from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.prompts.analytics_prompts import ANALYTICS_SYSTEM_PROMPT
from src.schemas.analytics_schemas import (
    AnalyticsInsight,
    AnalyticsMetric,
    AnalyticsQuery,
    AnalyticsResponse,
)
from src.services.github_service import GitHubService
from src.services.llm_service import LLMService
from src.utils.json_parser import parse_generic_json_response


class AnalyticsValidationError(Exception):
    """Llançat quan les dades o la consulta analítica no compleixen les validacions requerides."""


class AnalyticsProcessingError(Exception):
    """Llançat quan es produeix un error en la comunicació amb el motor o durant el processament."""


class AnalyticsAgent(BaseAgent):
    """Agent d'IA dedicat a l'anàlisi de dades, detecció de patrons i generació de conclusions."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        github_service: Optional[GitHubService] = None,
        repo_name: Optional[str] = None,
    ) -> None:
        """Inicialitza l'AnalyticsAgent amb serveis i logger configurats.

        Args:
            llm_service: Instància opcional de LLMService per a injecció de dependències.
            github_service: Instància opcional de GitHubService per a injecció de dependències.
            repo_name: Nom opcional del repositori actiu.
        """
        super().__init__(
            agent_name="AnalyticsAgent",
            llm_service=llm_service,
            github_service=github_service,
            repo_name=repo_name,
        )

    def validate_request(
        self,
        query: str | AnalyticsQuery,
        data: Optional[dict[str, Any] | list[Any]] = None,
    ) -> AnalyticsQuery:
        """Valida la coherència i format de la petició analítica.

        Args:
            query: Objecte `AnalyticsQuery` o text en llenguatge natural.
            data: Dades a analitzar si `query` s'introdueix com a text.

        Returns:
            AnalyticsQuery: Petició validada i estructurada.

        Raises:
            AnalyticsValidationError: Si falten dades, el text és buit o el format és invàlid.
        """
        if isinstance(query, AnalyticsQuery):
            return query

        if not isinstance(query, str) or not query.strip():
            raise AnalyticsValidationError("La consulta analítica no pot estar buida ni ser invàlida.")

        if data is None:
            raise AnalyticsValidationError("Cal proporcionar un conjunt de dades analitzable (diccionari o llista).")

        if not isinstance(data, (dict, list)):
            raise AnalyticsValidationError(
                f"Format de dades incompatible: s'esperava dict o list, s'ha rebut {type(data).__name__}."
            )

        if not data:
            raise AnalyticsValidationError("El conjunt de dades proporcionat és buit.")

        try:
            return AnalyticsQuery(query=query.strip(), data_payload=data)
        except Exception as err:
            raise AnalyticsValidationError(f"Error de validació de la sol·licitud: {err}") from err

    def _build_user_prompt(self, request: AnalyticsQuery) -> str:
        """Construeix el prompt que es transmetrà al model de llenguatge.

        Args:
            request: Objecte `AnalyticsQuery` amb la consulta i el payload de dades.

        Returns:
            str: Text del prompt amb les dades serialitzades en JSON.
        """
        payload_serialized = json.dumps(request.data_payload, ensure_ascii=False, indent=2)
        context_line = f"Context addicional: {request.context}\n" if request.context else ""
        return (
            f"Consulta analítica: {request.query}\n"
            f"{context_line}\n"
            f"Conjunt de dades a analitzar:\n"
            f"{payload_serialized}"
        )

    def _parse_model_output(self, raw_output: str) -> AnalyticsResponse:
        """Converteix la sortida del LLM en un objecte `AnalyticsResponse` validat.

        Args:
            raw_output: Text JSON generat pel model LLM.

        Returns:
            AnalyticsResponse: Resposta estructurada.

        Raises:
            AnalyticsProcessingError: Si la sortida no es pot convertir a l'esquema esperat.
        """
        try:
            parsed = parse_generic_json_response(
                raw_output, expected_keys=("summary", "insights", "metrics")
            )
            if not parsed or not isinstance(parsed, dict):
                raise ValueError("No s'ha obtingut un diccionari vàlid de la sortida del model.")

            insights = [
                AnalyticsInsight(**item) if isinstance(item, dict) else item
                for item in parsed.get("insights", [])
            ]
            metrics = [
                AnalyticsMetric(**item) if isinstance(item, dict) else item
                for item in parsed.get("metrics", [])
            ]
            summary = str(parsed.get("summary", "Anàlisi completada.")).strip()
            status = parsed.get("status", "success")
            if status not in ("success", "partial", "error"):
                status = "success"

            return AnalyticsResponse(
                status=status,
                summary=summary,
                insights=insights,
                metrics=metrics,
                metadata=parsed.get("metadata", {}),
            )
        except Exception as exc:
            self.logger.warning(f"Error en interpretar la resposta del model: {exc}")
            raise AnalyticsProcessingError(f"No s'ha pogut interpretar la resposta analítica: {exc}") from exc

    def analyze(
        self,
        query: str | AnalyticsQuery,
        data: Optional[dict[str, Any] | list[Any]] = None,
    ) -> AnalyticsResponse:
        """Executa el procés d'anàlisi de dades i retorna conclusions estructurades.

        Args:
            query: Cadena amb la pregunta analítica o instància d'AnalyticsQuery.
            data: Dades a processar (opcional si ja venen a `query`).

        Returns:
            AnalyticsResponse: Resum, observacions i mètriques calculades.

        Raises:
            AnalyticsValidationError: Si els paràmetres d'entrada són incorrectes o buits.
            AnalyticsProcessingError: Si es produeix una fallada en el motor LLM o al processament.
        """
        request = self.validate_request(query, data)
        self.logger.info(f"Iniciant anàlisi per a la consulta: '{request.query}'")

        user_prompt = self._build_user_prompt(request)
        try:
            raw_response = self.llm.generate_task_spec(
                user_requirement=user_prompt,
                system_prompt=ANALYTICS_SYSTEM_PROMPT,
                response_schema=AnalyticsResponse,
            )
        except Exception as exc:
            self.logger.error(f"Fallada en comunicar amb el model LLM durant l'anàlisi: {exc}")
            raise AnalyticsProcessingError(f"Error en comunicar amb el motor analític: {exc}") from exc

        response = self._parse_model_output(raw_response)
        self.logger.info(f"Anàlisi finalitzada amb èxit. Estat: {response.status}, Insights: {len(response.insights)}")
        return response
