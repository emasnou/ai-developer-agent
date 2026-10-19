"""Agent desenvolupador encarregat de generar codi basat en les especificacions."""

from typing import Any, Dict
from src.utils.logger import AgentAdapter, get_agent_logger


class DeveloperAgent:
    """Classe que representa el DeveloperAgent amb suport de logging estructurat."""

    def __init__(self, agent_id: str = "DeveloperAgent") -> None:
        """Inicialitza el DeveloperAgent i el seu logger corresponent."""
        self.agent_id: str = agent_id
        base_logger = get_agent_logger(self.agent_id)
        self.logger: AgentAdapter = AgentAdapter(base_logger, {"agent_id": self.agent_id})

    def implement_task(self, task_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Implementa una tasca de desenvolupament i registra l'activitat.

        Args:
            task_spec (Dict[str, Any]): Especificació de la tasca.

        Returns:
            Dict[str, Any]: Resultat de la implementació.
        """
        self.logger.info(f"Iniciant implementació de la tasca: {task_spec.get('title', 'Sense títol')}")
        try:
            # Lògica d'implementació simulada o existent
            implementation_result = {"status": "success", "files_modified": 1}
            self.logger.info("Tasca implementada correctament")
            return implementation_result
        except Exception as e:
            self.logger.error(f"Error durant la implementació de la tasca: {str(e)}")
            raise
