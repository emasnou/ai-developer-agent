import time
from google import genai
from google.genai import types
from google.genai.errors import ServerError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.utils.config import GEMINI_API_KEY

class LLMService:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("Falta la variable GEMINI_API_KEY al fitxer .env")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Models actuals recomanats per a tasques d'agents i codificació
        self.primary_model = "gemini-3.8-flash"
        self.fallback_model = "gemini-3.5-flash-lite"

    @retry(
        retry=retry_if_exception_type((ServerError, APIError)),
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        before_sleep=lambda retry_state: print(
            f"⚠️ Pic d'alta demanda a l'API de Gemini (503). Reintentant en {retry_state.next_action.sleep:.1f} segons..."
        )
    )
    def _call_gemini_with_retry(self, prompt: str, model_name: str, force_json: bool = True) -> str:
        """Crida interna a l'API de Gemini amb reintents automàtics i opció de JSON forçat."""
        
        # Configurem el paràmetre response_mime_type si volem forçar JSON
        config_args = {
            "temperature": 0.2
        }
        if force_json:
            config_args["response_mime_type"] = "application/json"

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_args)
        )
        return response.text

    def generate_task_spec(self, user_requirement: str, system_prompt: str) -> str:
        """Envia el requeriment a Gemini gestionant reintents i model de reserva."""
        prompt_complet = f"{system_prompt}\n\nRequeriment de l'aplicació:\n{user_requirement}"
        
        try:
            print(f"🤖 [LLMService] Enviant petició al model '{self.primary_model}'...")
            return self._call_gemini_with_retry(prompt_complet, self.primary_model, force_json=True)
        except Exception as e:
            print(f"⚠️ El model principal '{self.primary_model}' no ha pogut respondre. Utilitzant el model de reserva '{self.fallback_model}'...")
            try:
                return self._call_gemini_with_retry(prompt_complet, self.fallback_model, force_json=True)
            except Exception as final_error:
                print(f"❌ Error persistent en la connexió amb Gemini: {final_error}")
                raise final_error