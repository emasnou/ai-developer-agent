"""Servei de comunicació resilient amb l'API de Google Gemini."""

from __future__ import annotations

from typing import Any, Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError, ServerError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.utils.config import AppConfig
from src.utils.logger import AgentLogger, StructuredAgentAdapter


class LLMService:
    """Client de Google Gemini amb suport de Structured Outputs, reintents exponencials i fallback."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Inicialitza el client de Gemini i configura els models primari i de reserva.

        Args:
            api_key: Clau d'API de Gemini opcional (si no s'indica, es llegeix de l'entorn).

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

        # Models actuals recomanats per a tasques d'agents i codificació
        self.primary_model: str = "gemini-3.8-flash"
        self.fallback_model: str = "gemini-3.5-flash-lite"


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

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_args),
        )
        return response.text or ""

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
