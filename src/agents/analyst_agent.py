"""Agent analista encarregat d'analitzar issues i generar especificacions."""

from typing import Any, Dict
from src.utils.logger import AgentAdapter, get_agent_logger


class AnalystAgent:
    """Classe que representa l'AnalystAgent amb suport de logging estructurat."""

    def __init__(self, agent_id: str = "AnalystAgent") -> None:
        """Inicialitza l'AnalystAgent i el seu logger corresponent."""
        self.agent_id: str = agent_id
        base_logger = get_agent_logger(self.agent_id)
        self.logger: AgentAdapter = AgentAdapter(base_logger, {"agent_id": self.agent_id})

    def analyze_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analitza una issue de GitHub i registra l'activitat.

        Args:
            issue_data (Dict[str, Any]): Dades de la issue.

        Returns:
            Dict[str, Any]: Resultat de l'anàlisi.
        """
        self.logger.info(f"Iniciant anàlisi de la issue: {issue_data.get('title', 'Sense títol')}")
        try:
            # Lògica d'anàlisi simulada o existent
            analysis_result = {"status": "success", "details": "Anàlisi completada correctament"}
            self.logger.info("Anàlisi de la issue finalitzada amb èxit")
            return analysis_result
        except Exception as e:
            self.logger.error(f"Error durant l'anàlisi de la issue: {str(e)}")
            raise
