"""Tests unitaris per validar l'estructura d'ADRs, la plantilla d'Agent IA i l'esquema Pydantic."""

from __future__ import annotations

from pathlib import Path

from src.schemas.agent_schemas import ADRAlternative, ArchitectureDecisionRecord


def test_adr_directory_and_template_structure_exist() -> None:
    """Comprova que el directori docs/adr/ i la plantilla 0000 existeixen amb les seccions clau."""
    adr_dir = Path("docs/adr")
    template_file = adr_dir / "0000-template-adr-agent-ia.md"
    readme_file = adr_dir / "README.md"
    policy_file = Path("docs/code_policy.md")

    assert adr_dir.exists() and adr_dir.is_dir()
    assert template_file.exists()
    assert readme_file.exists()
    assert policy_file.exists()

    template_text = template_file.read_text(encoding="utf-8")
    assert "## 📋 Metadades i Traçabilitat de l'Agent d'IA" in template_text
    assert "## 1. Context i Problema Tècnic" in template_text
    assert "## 2. Factors de Decisió" in template_text
    assert "## 3. Decisió d'Arquitectura Presa per l'Agent IA" in template_text
    assert "## 4. Alternatives Considerades i Descartades" in template_text
    assert "## 5. Conseqüències, Trade-offs i Anàlisi de Seguretat (OWASP Top 10)" in template_text
    assert "## 6. Verificació Automatitzada i Evidència de QA (PyTest)" in template_text


def test_architecture_decision_record_pydantic_renders_valid_markdown(tmp_path: Path) -> None:
    """Verifica que un Agent IA pot generar un ADR tipat i serialitzar-lo a Markdown."""
    adr = ArchitectureDecisionRecord(
        adr_id="ADR-0003",
        title="Validació de Tokens amb HMAC-SHA256",
        status="Acceptat",
        date="2026-10-27",
        author_agent="DeveloperAgent",
        llm_model="gemini-2.5-flash",
        repository="emasnou/ai-developer-agent",
        issue_or_pr_ref="#42",
        owasp_impact="Alt — A02: Cryptographic Failures, A07: Authentication Failures",
        context="Cal signar tokens de recuperació sense emmagatzemar estat en text pla.",
        decision_drivers=[
            "Seguretat criptogràfica sense estat (stateless)",
            "Comparació en temps constant",
        ],
        decision_summary="S'adopta HMAC-SHA256 amb clau de mínim 32 caràcters i hmac.compare_digest.",
        affected_files=["src/password_reset.py", "tests/unit/test_password_reset.py"],
        alternatives=[
            ADRAlternative(
                option_name="HMAC-SHA256 (Seleccionada)",
                pros="Ràpid, estandarditzat i sense dependències externes",
                cons="Requereix rotació segura de APP_SECRET_KEY",
                decision_reason="Compleix NIST i OWASP A02 amb la llibreria estàndard",
            ),
            ADRAlternative(
                option_name="Tokens aleatoris en memòria sense signatura",
                pros="Implementació simple",
                cons="Perd estat si el procés es reinicia",
                decision_reason="Descartat per manca de persistència i verificació criptogràfica",
            ),
        ],
        positive_consequences=["Verificació criptogràfica immediata en temps constant"],
        tradeoffs=["Llista de revocació d'un sol ús mantinguda amb purga amortitzada"],
        security_assessment="Mitiga A02 i A07 utilitzant secrets i hmac.compare_digest.",
        verification_evidence="Validat amb pytest a tests/unit/test_password_reset.py.",
    )

    md_output = adr.to_markdown()
    output_file = tmp_path / "0003-validacio-tokens-hmac.md"
    output_file.write_text(md_output, encoding="utf-8")

    saved = output_file.read_text(encoding="utf-8")
    assert "# ADR-0003: Validació de Tokens amb HMAC-SHA256" in saved
    assert "| **Agent Autor** | `DeveloperAgent` |" in saved
    assert "| **Repositori Actiu** | `emasnou/ai-developer-agent` |" in saved
    assert "| **HMAC-SHA256 (Seleccionada)** |" in saved
    assert "tests/unit/test_password_reset.py" in saved

