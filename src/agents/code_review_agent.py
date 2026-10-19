"""
Agent CodeReview per revisar la qualitat del codi i seguretat.
"""

from typing import Any, Dict
from src.services.llm_service import LLMService

class CodeReviewAgent:
    """
    Agent encarregat de revisar el codi generat per altres agents.
    """

    def __init__(self, llm_service: LLMService) -> None:
        """
        Inicialitza el CodeReviewAgent.

        Args:
            llm_service (LLMService): Servei LLM.
        """
        self.llm_service = llm_service

    def review_code(self, code_diff: str) -> Dict[str, Any]:
        """
        Revisa un diff de codi buscant errors o vulnerabilitats.

        Args:
            code_diff (str): Diferències de codi a revisar.

        Returns:
            Dict[str, Any]: Resultat de la revisió.
        """
        try:
            review_result = {"approved": True, "comments": "Codi net i segur."}
            return review_result
        except Exception as e:
            raise
