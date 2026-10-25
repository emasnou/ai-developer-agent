"""Esquemes de dades Pydantic per a les sortides estructurades (Structured Outputs) dels agents."""

from typing import List, Literal

from pydantic import BaseModel, Field

class FileItem(BaseModel):
    """Representa un fitxer de codi que s'ha de crear o modificar."""
    path: str = Field(description="Camí relatiu del fitxer dins del repositori (p.ex. 'src/module.py')")
    action: Literal["create_or_modify", "modify", "create"] = Field(
        default="create_or_modify",
        description="Acció a realitzar: create_or_modify, modify o create"
    )
    content: str = Field(description="Contingut complet i executable del fitxer Python")

class DeveloperPlan(BaseModel):
    """Pla de canvis complet generat per l'agent desenvolupador."""
    summary: str = Field(description="Resum breu de les modificacions realitzades")
    files: List[FileItem] = Field(description="Llista de fitxers modificats o creats")

class CodeReviewResponse(BaseModel):
    """Estructura de la revisió de codi generada pel CodeReviewAgent."""
    approved: bool = Field(description="Indica si la PR està aprovada (True) o si calen canvis (False)")
    report: str = Field(description="Informe detallat de l'auditoria en format Markdown")

class ImprovementItem(BaseModel):
    """Tasca o suggeriment de millora futura detectada al Code Review."""
    title: str = Field(description="Títol de la Issue de millora amb el prefix 'enhancement:'")
    description: str = Field(description="Descripció completa de la millora en format Markdown")

class ImprovementsResponse(BaseModel):
    """Llista de millores a futur extretes pel CodeReviewAgent."""
    improvements: List[ImprovementItem] = Field(description="Llista de millores futures identificades")

