"""Esquemes de dades Pydantic per a les sortides estructurades (Structured Outputs) dels agents.

Actuen com a contracte de dades i documentació viva entre els models LLM (Google Gemini)
i els agents autònoms (`DeveloperAgent`, `CodeReviewAgent`, `AnalystAgent`).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class FileItem(BaseModel):
    """Representa un fitxer de codi o documentació que s'ha de crear o modificar."""

    path: str = Field(
        description="Camí relatiu del fitxer dins del repositori (p.ex. 'src/module.py')"
    )
    action: Literal["create_or_modify", "modify", "create"] = Field(
        default="create_or_modify",
        description="Acció a realitzar: create_or_modify, modify o create",
    )
    content: str = Field(description="Contingut complet i executable del fitxer")


class ADRAlternative(BaseModel):
    """Representa una alternativa arquitectònica avaluada per l'agent d'IA."""

    option_name: str = Field(description="Nom descriptiu de l'opció o patró avaluat")
    pros: str = Field(description="Avantatges tècnics principals de l'opció")
    cons: str = Field(description="Inconvenients o costos associats")
    decision_reason: str = Field(
        description="Motiu pel qual s'ha seleccionat o descartat aquesta opció"
    )


class ArchitectureDecisionRecord(BaseModel):
    """Contracte estructurat per documentar un Architecture Decision Record (ADR) per un Agent IA."""

    adr_id: str = Field(description="Identificador de l'ADR (p.ex. 'ADR-0003')")
    title: str = Field(description="Títol breu i descriptiu de la decisió d'arquitectura")
    status: Literal["Proposat", "Acceptat", "Obsolet"] = Field(
        default="Proposat",
        description="Estat actual de l'ADR dins del cicle de vida",
    )
    date: str = Field(description="Data de la decisió en format ISO YYYY-MM-DD")
    author_agent: str = Field(
        default="DeveloperAgent",
        description="Agent d'IA o autor responsable de la decisió",
    )
    llm_model: str = Field(
        default="gemini-2.5-flash",
        description="Model LLM emprat durant el raonament arquitectònic",
    )
    repository: str = Field(description="Nom del repositori actiu en format 'propietari/repo'")
    issue_or_pr_ref: str = Field(description="Referència de la Issue o PR vinculada (p.ex. '#12')")
    owasp_impact: str = Field(
        description="Nivell d'impacte de seguretat i categories OWASP relacionades"
    )
    context: str = Field(description="Context tècnic, requeriment d'origen i restriccions")
    decision_drivers: list[str] = Field(
        description="Llista de factors clau de decisió (seguretat, SRP, testabilitat, rendiment)"
    )
    decision_summary: str = Field(
        description="Explicació detallada de la decisió presa i el seu perquè"
    )
    affected_files: list[str] = Field(
        description="Llista de rutes de fitxers creats o modificats per aquesta decisió"
    )
    alternatives: list[ADRAlternative] = Field(
        description="Alternatives considerades i comparades per l'agent d'IA"
    )
    positive_consequences: list[str] = Field(
        description="Beneficis tècnics derivats de la decisió"
    )
    tradeoffs: list[str] = Field(
        description="Compromisos assumits o limitacions conegudes i la seva mitigació"
    )
    security_assessment: str = Field(
        description="Avaluació de vectors OWASP Top 10 mitigats i aïllament de secrets"
    )
    verification_evidence: str = Field(
        description="Tests unitaris (PyTest) i criteris de validació que demostren la decisió"
    )

    def to_markdown(self) -> str:
        """Renderitza el registre ADR en format Markdown seguint `0000-template-adr-agent-ia.md`.

        Returns:
            str: Contingut complet del fitxer Markdown de l'ADR.
        """
        drivers_md = "\n".join(f"* {driver}" for driver in self.decision_drivers)
        files_md = "\n".join(f"* `{path}`" for path in self.affected_files)
        positives_md = "\n".join(f"* ✅ {item}" for item in self.positive_consequences)
        tradeoffs_md = "\n".join(f"* ⚠️ {item}" for item in self.tradeoffs)
        alt_rows = "\n".join(
            f"| **{alt.option_name}** | {alt.pros} | {alt.cons} | {alt.decision_reason} |"
            for alt in self.alternatives
        )

        return (
            f"# {self.adr_id}: {self.title}\n\n"
            "## 📋 Metadades i Traçabilitat de l'Agent d'IA\n\n"
            "| Camp | Valor |\n"
            "| :--- | :--- |\n"
            f"| **ID d'ADR** | `{self.adr_id}` |\n"
            f"| **Estat** | `{self.status}` |\n"
            f"| **Data** | `{self.date}` |\n"
            f"| **Agent Autor** | `{self.author_agent}` |\n"
            f"| **Model LLM Emprat** | `{self.llm_model}` |\n"
            f"| **Repositori Actiu** | `{self.repository}` |\n"
            f"| **Issue / PR Vinculada** | `{self.issue_or_pr_ref}` |\n"
            f"| **Impacte de Seguretat (OWASP)** | `{self.owasp_impact}` |\n\n"
            "---\n\n"
            "## 1. Context i Problema Tècnic\n\n"
            f"{self.context}\n\n"
            "---\n\n"
            "## 2. Factors de Decisió (Architectural Drivers)\n\n"
            f"{drivers_md}\n\n"
            "---\n\n"
            "## 3. Decisió d'Arquitectura Presa per l'Agent IA\n\n"
            "### 3.1. Resum de la Solució Escollida\n"
            f"{self.decision_summary}\n\n"
            "### 3.2. Components i Fitxers Afectats\n"
            f"{files_md}\n\n"
            "---\n\n"
            "## 4. Alternatives Considerades i Descartades\n\n"
            "| Alternativa Avaluada | Avantatges (Pros) | Inconvenients (Contres) | Motiu de Decisió |\n"
            "| :--- | :--- | :--- | :--- |\n"
            f"{alt_rows}\n\n"
            "---\n\n"
            "## 5. Conseqüències, Trade-offs i Anàlisi de Seguretat (OWASP Top 10)\n\n"
            "### 5.1. Conseqüències Positives\n"
            f"{positives_md}\n\n"
            "### 5.2. Trade-offs i Deute Tècnic Assumit\n"
            f"{tradeoffs_md}\n\n"
            "### 5.3. Avaluació de Seguretat (OWASP Top 10)\n"
            f"{self.security_assessment}\n\n"
            "---\n\n"
            "## 6. Verificació Automatitzada i Evidència de QA (PyTest)\n\n"
            f"{self.verification_evidence}\n"
        )




class CodeReviewResponse(BaseModel):
    """Estructura de la revisió de codi generada pel CodeReviewAgent."""

    approved: bool = Field(
        description="Indica si la PR està aprovada (True) o si calen canvis (False)"
    )
    report: str = Field(description="Informe detallat de l'auditoria en format Markdown")


class ImprovementItem(BaseModel):
    """Tasca o suggeriment de millora futura detectada al Code Review."""

    title: str = Field(description="Títol de la Issue de millora amb el prefix 'enhancement:'")
    description: str = Field(description="Descripció completa de la millora en format Markdown")


class ImprovementsResponse(BaseModel):
    """Llista de millores a futur extretes pel CodeReviewAgent."""

    improvements: list[ImprovementItem] = Field(
        description="Llista de millores futures identificades"
    )
