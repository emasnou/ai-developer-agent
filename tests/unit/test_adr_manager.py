"""Tests unitaris per a la utilitat de generació i gestió d'ADRs (Docs-as-Code)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.developer_agent import DeveloperAgent
from src.schemas.agent_schemas import ADRAlternative, ArchitectureDecisionRecord
from src.utils.adr_manager import (
    build_adr_filename,
    get_next_adr_id,
    materialize_adr_file,
    slugify_title,
)


def test_slugify_title_clean_and_safe() -> None:
    """Verifica que la sanitització del títol elimini accents i caràcters perillosos."""
    raw = "Elecció del motor de persistència / BD: SQL vs NoSQL?!"
    slug = slugify_title(raw)
    assert "persistencia" in slug
    assert "/" not in slug
    assert ":" not in slug
    assert "?" not in slug
    assert "!" not in slug
    assert slug.islower()


def test_slugify_title_empty_fallback() -> None:
    """Comprova que un títol buit o només caràcters especials retorni un valor per defecte."""
    assert slugify_title("???///***") == "decisio-arquitectura"


def test_get_next_adr_id_empty_directory(tmp_path: Path) -> None:
    """Comprova que en un directori sense fitxers es comenci pel '0001'."""
    empty_dir = tmp_path / "adr"
    assert get_next_adr_id(empty_dir) == "0001"


def test_get_next_adr_id_sequential(tmp_path: Path) -> None:
    """Valida la resolució de l'identificador seqüencial considerant fitxers previs."""
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0000-template.md").write_text("# Template", encoding="utf-8")
    (adr_dir / "0001-pydantic.md").write_text("# ADR 1", encoding="utf-8")
    (adr_dir / "0002-multi-repo.md").write_text("# ADR 2", encoding="utf-8")
    (adr_dir / "README.md").write_text("# Index", encoding="utf-8")

    next_id = get_next_adr_id(adr_dir)
    assert next_id == "0003"


def test_build_adr_filename() -> None:
    """Comprova la combinació d'identificador seqüencial i títol formatat."""
    filename = build_adr_filename("0004", "Integració de Motor SQLite")
    assert filename == "0004-integracio-de-motor-sqlite.md"


def test_materialize_adr_file_valid_creation(tmp_path: Path) -> None:
    """Comprova que materialize_adr_file escrigui un fitxer Markdown ben estructurat."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_record = ArchitectureDecisionRecord(
        adr_id="ADR-PENDING",
        title="Elecció de Base de Dades",
        status="Acceptat",
        date="2026-10-27",
        author_agent="DeveloperAgent",
        llm_model="gemini-3.8-flash",
        repository="owner/repo",
        issue_or_pr_ref="#15",
        owasp_impact="Mitigació d'injecció SQL (OWASP A03)",
        context="Necessitat d'un emmagatzematge ràpid i transaccional.",
        decision_drivers=["Rendiment", "Seguretat"],
        decision_summary="Adopció de SQLite amb ORM tipat.",
        affected_files=["src/db.py"],
        alternatives=[
            ADRAlternative(
                option_name="PostgreSQL",
                pros="Més robust",
                cons="Requereix servidor extern",
                decision_reason="Massa pesat per a un agent local",
            )
        ],
        positive_consequences=["Lleuger i integrable en memòria"],
        tradeoffs=["Concurrència limitada d'escriptura"],
        security_assessment="Paràmetres vinculats de forma segura.",
        verification_evidence="Cobert pel conjunt de tests unitaris.",
    )

    created_file = materialize_adr_file(adr_record, adr_dir)
    assert created_file.exists()
    assert created_file.name == "0001-eleccio-de-base-de-dades.md"
    content = created_file.read_text(encoding="utf-8")
    assert "ADR-0001: Elecció de Base de Dades" in content
    assert "## 1. Context i Problema Tècnic" in content
    assert "## 2. Factors de Decisió" in content
    assert "PostgreSQL" in content


def test_developer_agent_applies_adr_in_workspace(tmp_path: Path) -> None:
    """Verifica que DeveloperAgent apliqui l'ADR quan DeveloperPlan inclou decisió arquitectural."""
    agent = DeveloperAgent(
        llm_service=MagicMock(),
        github_service=MagicMock(),
        repo_name="test/repo",
    )
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)
    docs_adr = workspace_dir / "docs" / "adr"
    docs_adr.mkdir(parents=True)

    adr_dict = {
        "adr_id": "ADR-0001",
        "title": "Patró Repository",
        "status": "Acceptat",
        "date": "2026-10-27",
        "author_agent": "DeveloperAgent",
        "llm_model": "gemini-3.8-flash",
        "repository": "test/repo",
        "issue_or_pr_ref": "#4",
        "owasp_impact": "Mitigació d'accés no segur",
        "context": "Context de prova",
        "decision_drivers": ["Testabilitat"],
        "decision_summary": "Utilització de repositories",
        "affected_files": ["src/repo.py"],
        "alternatives": [
            {
                "option_name": "Active Record",
                "pros": "Ràpid",
                "cons": "Acoblament fort",
                "decision_reason": "Manca d'aïllament",
            }
        ],
        "positive_consequences": ["Desacoblament"],
        "tradeoffs": ["Boilerplate"],
        "security_assessment": "Segur per disseny",
        "verification_evidence": "pytest tests/",
    }
    plan_data = {
        "summary": "Refactor arquitectural",
        "files": [{"path": "src/repo.py", "action": "create", "content": "# codi"}],
        "adr": adr_dict,
    }

    updated_files = agent._apply_adr_plan_if_present(
        plan_data, list(plan_data["files"]), workspace_dir
    )
    assert any("docs/adr/0001-patro-repository.md" in f["path"] for f in updated_files)
    assert (workspace_dir / "docs" / "adr" / "0001-patro-repository.md").is_file()
