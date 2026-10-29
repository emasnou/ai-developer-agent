"""Servei de comunicació resilient amb l'API de Google Gemini."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError, ServerError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.schemas.finops_schemas import TokenUsage
from src.services.metrics_tracker import DEFAULT_METRICS_FILE, MetricsTracker
from src.utils.config import AppConfig
from src.utils.logger import AgentLogger, StructuredAgentAdapter


class LLMService:
    """Client de Google Gemini amb suport de Structured Outputs, reintents exponencials i fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        metrics_tracker: Optional[MetricsTracker] = None,
        metrics_file: Optional[Path | str] = DEFAULT_METRICS_FILE,
    ) -> None:
        """Inicialitza el client de Gemini i configura els models primari i de reserva.

        Args:
            api_key: Clau d'API de Gemini opcional (si no s'indica, es llegeix de l'entorn).
            metrics_tracker: Gestor de telemetria i costos FinOps opcional.
            metrics_file: Fitxer JSONL de persistència per a les mètriques (None per desactivar).

        Raises:
            ValueError: Si falta la variable GEMINI_API_KEY.
        """
        cfg = AppConfig.from_env()
        resolved_key = api_key or cfg.gemini_api_key
        if not resolved_key:
            raise ValueError("Falta la variable GEMINI_API_KEY al fitxer .env")

        base_logger = AgentLogger.get_logger("LLMService")
        self.logger = StructuredAgentAdapter(base_logger, "LLMService")
        self.client = genai.Client(api_key=resolved_key)
        self.metrics_tracker: MetricsTracker = metrics_tracker or MetricsTracker()
        self.metrics_file: Optional[Path] = Path(metrics_file) if metrics_file else None

        # Models actuals recomanats per a tasques d'agents i codificació
        self.primary_model: str = "gemini-3.8-flash"
        self.fallback_model: str = "gemini-3.5-flash-lite"

    @staticmethod
    def _extract_token_usage(
        response: Any,
        prompt: str,
        system_instruction: Optional[str],
        output_text: str,
    ) -> TokenUsage:
        """Extreu les metadades d'ús de tokens de la resposta de Gemini o n'estima el volum.

        Args:
            response: Objecte de resposta retornat per `client.models.generate_content`.
            prompt: Text d'entrada enviat al model.
            system_instruction: Instrucció de sistema opcional.
            output_text: Text de resposta generat pel model.

        Returns:
            TokenUsage: Esquema validat amb el recompte de tokens d'entrada, cau i sortida.
        """
        meta = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(meta, "prompt_token_count", 0) or 0) if meta else 0
        completion_tokens = int(getattr(meta, "candidates_token_count", 0) or 0) if meta else 0
        cached_tokens = int(getattr(meta, "cached_content_token_count", 0) or 0) if meta else 0

        if prompt_tokens <= 0 and prompt:
            raw_input_len = len(prompt) + len(system_instruction or "")
            prompt_tokens = max(1, raw_input_len // 4)
        if completion_tokens <= 0 and output_text:
            completion_tokens = max(1, len(output_text) // 4)

        cached_tokens = max(0, min(cached_tokens, prompt_tokens))
        return TokenUsage(
            prompt_tokens=max(0, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
            cached_tokens=cached_tokens,
        )

    def _record_call_telemetry(
        self,
        model_name: str,
        usage: TokenUsage,
        duration_seconds: float,
    ) -> None:
        """Registra la telemetria de la crida al MetricsTracker i al fitxer persistent JSONL.

        Args:
            model_name: Nom del model utilitzat.
            usage: Dades de consum de tokens.
            duration_seconds: Durada de la crida en segons.
        """
        try:
            record = self.metrics_tracker.record_call(
                model_name=model_name,
                usage=usage,
                duration_seconds=duration_seconds,
            )
            if self.metrics_file is not None:
                self.metrics_tracker.append_record_to_file(record, self.metrics_file)
        except Exception as exc:
            self.logger.warning(f"No s'ha pogut enregistrar la telemetria FinOps: {exc}")


    @retry(
        retry=retry_if_exception_type((ServerError, APIError)),
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        before_sleep=lambda retry_state: print(
            f"⚠️ Pic d'alta demanda a l'API de Gemini (503). "
            f"Reintentant en {retry_state.next_action.sleep:.1f} segons..."
        ),
    )
    def _call_gemini_with_retry(
        self,
        prompt: str,
        model_name: str,
        system_instruction: Optional[str] = None,
        force_json: bool = True,
        response_schema: Optional[Any] = None,
    ) -> str:
        """Executa la crida a l'API de Gemini amb reintents exponencials i configuració d'esquema.

        Args:
            prompt: Contingut de la petició d'usuari.
            model_name: Identificador del model de Gemini a invocar.
            system_instruction: Instrucció de sistema opcional per guiar el rol del model.
            force_json: Si és True i no hi ha `response_schema`, força `application/json`.
            response_schema: Esquema Pydantic opcional per a Structured Outputs.

        Returns:
            str: Text de resposta generat pel model.

        Raises:
            ServerError: Si l'API de Gemini retorna un error de servidor 5xx després dels reintents.
            APIError: Si l'API retorna un error de client o quota.
        """
        config_args: dict[str, Any] = {"temperature": 0.2}
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        if response_schema:
            config_args["response_schema"] = response_schema
            config_args["response_mime_type"] = "application/json"
        elif force_json:
            config_args["response_mime_type"] = "application/json"

        start_time = time.perf_counter()
        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_args),
        )
        duration = max(0.0, time.perf_counter() - start_time)
        output_text = response.text or ""
        usage = self._extract_token_usage(
            response=response,
            prompt=prompt,
            system_instruction=system_instruction,
            output_text=output_text,
        )
        self._record_call_telemetry(
            model_name=model_name,
            usage=usage,
            duration_seconds=duration,
        )
        return output_text

    def generate_task_spec(
        self,
        user_requirement: str,
        system_prompt: str,
        force_json: bool = True,
        response_schema: Optional[Any] = None,
    ) -> str:
        """Envia una petició a Gemini gestionant reintents automàtics i el model de reserva.

        Args:
            user_requirement: Prompt principal amb les dades de la tasca.
            system_prompt: Prompt de sistema que defineix les regles de l'agent.
            force_json: Si és True, sol·licita resposta en format MIME `application/json`.
            response_schema: Classe Pydantic opcional per garantir l'estructura del JSON.

        Returns:
            str: Contingut generat pel model primari o pel model de reserva (fallback).

        Raises:
            Exception: Si tant el model principal com el model de reserva fallen.
        """
        try:
            self.logger.info(f"Enviant petició al model principal '{self.primary_model}'...")
            print(f"🤖 [LLMService] Enviant petició al model '{self.primary_model}'...")
            return self._call_gemini_with_retry(
                prompt=user_requirement,
                model_name=self.primary_model,
                system_instruction=system_prompt,
                force_json=force_json,
                response_schema=response_schema,
            )
        except Exception as e:
            self.logger.warning(
                f"El model '{self.primary_model}' ha fallat ({e}). Activant fallback '{self.fallback_model}'."
            )
            print(
                f"⚠️ El model principal '{self.primary_model}' no ha pogut respondre ({e}). "
                f"Utilitzant el model de reserva '{self.fallback_model}'..."
            )
            try:
                return self._call_gemini_with_retry(
                    prompt=user_requirement,
                    model_name=self.fallback_model,
                    system_instruction=system_prompt,
                    force_json=force_json,
                    response_schema=response_schema,
                )
            except Exception as final_error:
                self.logger.error(f"Error persistent en la connexió amb Gemini: {final_error}")
                print(f"❌ Error persistent en la connexió amb Gemini: {final_error}")
                raise
