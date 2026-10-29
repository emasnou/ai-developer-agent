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

# Límit de seguretat per defecte (10 MB) per prevenir exhauriment de memòria (OWASP A04 - DoS/OOM)
DEFAULT_MAX_PAYLOAD_SIZE: int = 10 * 1024 * 1024


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
        max_payload_size: int = DEFAULT_MAX_PAYLOAD_SIZE,    
    ) -> None:    
        """Inicialitza l'AnalyticsAgent amb serveis, logger i llindar màxim de càrrega útil.    

        Args:    
            llm_service: Instància opcional de LLMService per a injecció de dependències.    
            github_service: Instància opcional de GitHubService per a injecció de dependències.    
            repo_name: Nom opcional del repositori actiu.    
            max_payload_size: Mida màxima en bytes permesa per a les dades analitzades.    
        """    
        super().__init__(    
            agent_name="AnalyticsAgent",    
            llm_service=llm_service,    
            github_service=github_service,    
            repo_name=repo_name,    
        )    
        self.max_payload_size: int = max_payload_size    

    def _check_payload_size(    
        self, data_payload: dict[str, Any] | list[Any], max_allowed_bytes: int    
    ) -> None:    
        """Calcula la mida del payload serialitzat i valida que no superi el límit permès.    

        Args:    
            data_payload: Dades estructurades a inspeccionar.    
            max_allowed_bytes: Nombre màxim de bytes tolerats abans de rebutjar la petició.    

        Raises:    
            AnalyticsValidationError: Si el payload no és serialitzable o supera el llindar màxim.    
        """    
        try:    
            # Calculem la mida en bytes serialitzats UTF-8 per mitigar atacs DoS/OOM (OWASP A04)    
            serialized = json.dumps(data_payload, ensure_ascii=False).encode("utf-8")    
        except (TypeError, ValueError) as exc:    
            raise AnalyticsValidationError(    
                f"El conjunt de dades no és serialitzable en format JSON: {exc}"    
            ) from exc    

        payload_size = len(serialized)    
        if payload_size > max_allowed_bytes:    
            raise AnalyticsValidationError(    
                f"La mida de les dades ({payload_size} bytes) supera el límit màxim permès "    
                f"de {max_allowed_bytes} bytes."    
            )    

    def validate_request(    
        self,    
        query: str | AnalyticsQuery,    
        data: Optional[dict[str, Any] | list[Any]] = None,    
        max_payload_size: Optional[int] = None,    
    ) -> AnalyticsQuery:    
        """Valida la coherència, format i mida màxima de la petició analítica.    

        Args:    
            query: Objecte `AnalyticsQuery` o text en llenguatge natural.    
            data: Dades a analitzar si `query` s'introdueix com a text.    
            max_payload_size: Llindar de mida màxima en bytes opcional per sobreescriure el de la instància.    

        Returns:    
            AnalyticsQuery: Petició validada i estructurada.    

        Raises:    
            AnalyticsValidationError: Si falten dades, el format és invàlid o se supera el límit de mida.    
        """    
        effective_limit = (    
            max_payload_size if max_payload_size is not None else self.max_payload_size    
        )    

        if isinstance(query, AnalyticsQuery):    
            self._check_payload_size(query.data_payload, effective_limit)    
            return query    

        if not isinstance(query, str) or not query.strip():    
            raise AnalyticsValidationError("La consulta analítica no pot estar buida ni ser invàlida.")    

        if data is None:    
            raise AnalyticsValidationError(    
                "Cal proporcionar un conjunt de dades analitzable (diccionari o llista)."    
            )    

        if not isinstance(data, (dict, list)):    
            raise AnalyticsValidationError(    
                f"Format de dades incompatible: s'esperava dict o list, s'ha rebut {type(data).__name__}."    
            )    

        if not data:    
            raise AnalyticsValidationError("El conjunt de dades proporcionat és buit.")    

        self._check_payload_size(data, effective_limit)    

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
        max_payload_size: Optional[int] = None,    
    ) -> AnalyticsResponse:    
        """Executa el procés d'anàlisi de dades i retorna conclusions estructurades.    

        Args:    
            query: Cadena amb la pregunta analítica o instància d'AnalyticsQuery.    
            data: Dades a processar (opcional si ja venen a `query`).    
            max_payload_size: Mida màxima permesa en bytes per a aquesta execució específica.    

        Returns:    
            AnalyticsResponse: Resum, observacions i mètriques calculades.    

        Raises:    
            AnalyticsValidationError: Si els paràmetres d'entrada són incorrectes o superen la mida màxima.    
            AnalyticsProcessingError: Si es produeix una fallada en el motor LLM o al processament.    
        """    
        request = self.validate_request(query, data, max_payload_size=max_payload_size)    
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
