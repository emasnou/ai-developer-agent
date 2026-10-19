"""Agent de revisió de codi encarregat de validar la qualitat i seguretat."""

from typing import Any, Dict
from src.utils.logger import AgentAdapter, get_agent_logger


class CodeReviewAgent:
    """Classe que representa el CodeReviewAgent amb suport de logging estructurat."""

    def __init__(self, agent_id: str = "CodeReviewAgent") -> None:
        """Inicialitza el CodeReviewAgent i el seu logger corresponent."""
        self.agent_id: str = agent_id
        base_logger = get_agent_logger(self.agent_id)
        self.logger: AgentAdapter = AgentAdapter(base_logger, {"agent_id": self.agent_id})

    def review_code(self, pull_request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Revisa el codi d'una pull request i registra l'activitat.

        Args:
            pull_request_data (Dict[str, Any]): Dades de la pull request.

        Returns:
            Dict[str, Any]: Resultat de la revisió.
        """
        self.logger.info(f"Iniciant revisió de codi per a PR: {pull_request_data.get('id', 'N/A')}")
        try:
            # Lògica de revisió simulada o existent
            review_result = {"status": "approved", "comments": 0}
            self.logger.info("Revisió de codi completada sense incidències")
            return review_result
        except Exception as e:
            self.logger.error(f"Error durant la revisió de codi: {str(e)}")
            raise
