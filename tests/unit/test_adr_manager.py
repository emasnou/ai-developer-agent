"""Tests unitaris per a la gestió d'ADRs, ordenació numèrica i concurrència atòmica."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path

import pytest

from src.schemas.agent_schemas import ADRAlternative, ArchitectureDecisionRecord
from src.utils.adr_manager import (
    adr_lock,
    build_adr_filename,
    get_next_adr_id,
    materialize_adr_file,
    slugify_title,
)


def test_slugify_title_sanitizes_accents_and_special_characters() -> None:
    """Verifica que slugify_title elimini accents i caràcters especials per seguretat."""
    title = "Adopció de Caixà d'Alta Eficiència & Redis v2.0!"
    slug = slugify_title(title)
    assert "caixa" in slug
    assert "redis" in slug
    assert "!" not in slug
    assert "&" not in slug


def test_get_next_adr_id_empty_directory(tmp_path: Path) -> None:
    """Verifica que es retorni '0001' quan el directori està buit o no existeix."""
    assert get_next_adr_id(tmp_path / "sub_adr") == "0001"


def test_get_next_adr_id_ignores_template_0000(tmp_path: Path) -> None:
    """Verifica que la plantilla base 0000 sigui ignorada en el càlcul."""
    (tmp_path / "0000-template-adr-agent-ia.md").write_text("# ADR Template", encoding="utf-8")
    assert get_next_adr_id(tmp_path) == "0001"


def test_get_next_adr_id_strict_numeric_sorting(tmp_path: Path) -> None:
    """Verifica l'ordenació estrictament numèrica fins i tot amb nombres superiors a 9."""
    (tmp_path / "0001-primera.md").write_text("# 1", encoding="utf-8")
    (tmp_path / "0009-novena.md").write_text("# 9", encoding="utf-8")
    (tmp_path / "0010-desena.md").write_text("# 10", encoding="utf-8")
    (tmp_path / "0002-segona.md").write_text("# 2", encoding="utf-8")

    next_id = get_next_adr_id(tmp_path)
    assert next_id == "0011"


def _build_dummy_adr(title: str = "Decisió de Prova") -> ArchitectureDecisionRecord:
    """Crea una instància d'ArchitectureDecisionRecord per a tests."""
    return ArchitectureDecisionRecord(
        adr_id="ADR-0000",
        title=title,
        status="Acceptat",
        date="2026-03-30",
        author_agent="DeveloperAgent",
        llm_model="gemini-2.5-flash",
        repository="emasnou/ai-developer-agent",
        issue_or_pr_ref="#20",
        owasp_impact="A01 - Broken Access Control",
        context="Context tècnic de prova",
        decision_drivers=["Seguretat", "Rendiment"],
        decision_summary="Resum de la solució escollida",
        affected_files=["src/utils/adr_manager.py"],
        alternatives=[
            ADRAlternative(
                option_name="Opció A",
                pros="Més ràpida",
                cons="Més complexa",
                decision_reason="Millor rendiment",
            )
        ],
        positive_consequences=["Traçabilitat"],
        tradeoffs=["Cap conegut"],
        security_assessment="Mitigació d'atacs de concurrència",
        verification_evidence="PyTest tests/unit/test_adr_manager.py",
    )


def test_materialize_adr_file_creates_file_and_assigns_id(tmp_path: Path) -> None:
    """Verifica la creació física d'un ADR assignant l'identificador correcte."""
    adr_record = _build_dummy_adr(title="Adopció de Bloqueig Atòmic")
    created_path = materialize_adr_file(adr_record, tmp_path)

    assert created_path.exists()
    assert created_path.name.startswith("0001-adopcio-de-bloqueig-atomic")
    content = created_path.read_text(encoding="utf-8")
    assert "ADR-0001" in content
    assert "Adopció de Bloqueig Atòmic" in content


def test_materialize_adr_file_prevents_path_traversal(tmp_path: Path) -> None:
    """Verifica que no es pugui escapar del directori destí (OWASP A01)."""
    adr_record = _build_dummy_adr(title="../../etc/passwd")
    # slugify_title elimina caràcters perillosos i evita qualsevol path traversal
    created_path = materialize_adr_file(adr_record, tmp_path)
    assert created_path.is_relative_to(tmp_path.resolve())


def test_adr_concurrency_thread_safe(tmp_path: Path) -> None:
    """Verifica que crides concurrents des de múltiples fils creïn ADRs correlatius sense col·lisions."""
    num_threads = 5

    def _worker(idx: int) -> Path:
        rec = _build_dummy_adr(title=f"Tasca Concurrent {idx}")
        return materialize_adr_file(rec, tmp_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(_worker, i) for i in range(num_threads)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == num_threads
    files = sorted(tmp_path.glob("00*.md"))
    assert len(files) == num_threads
    prefixes = [f.name[:4] for f in files]
    assert prefixes == ["0001", "0002", "0003", "0004", "0005"]


def test_adr_lock_context_manager(tmp_path: Path) -> None:
    """Verifica que adr_lock s'adquireixi i alliberi sense errors."""
    with adr_lock(tmp_path):
        assert (tmp_path / ".adr.lock").exists()
