"""Tests unitaris per a l'automatització i validació de CHANGELOG.md (Keep a Changelog & SemVer)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.changelog_updater import (
    classify_commit_message,
    group_commits_by_category,
    main,
    release_unreleased_content,
    update_changelog_content,
    update_changelog_file,
)


def test_classify_commit_message_maps_to_keep_a_changelog_categories() -> None:
    """Verifica que els Conventional Commits es mapegen a Added, Changed, Fixed i Security."""
    assert classify_commit_message("feat(cli): afegir selector de repositoris") == (
        "Added",
        "**cli**: Afegir selector de repositoris",
    )
    assert classify_commit_message("fix: corregir descàrrega de branca en PR") == (
        "Fixed",
        "Corregir descàrrega de branca en PR",
    )
    assert classify_commit_message("security(auth): validació contra Path Traversal") == (
        "Security",
        "**auth**: Validació contra Path Traversal",
    )
    assert classify_commit_message("refactor(agents): extreure BaseAgent") == (
        "Changed",
        "**agents**: Extreure BaseAgent",
    )
    assert classify_commit_message("docs: actualitzar README i .env.example") == (
        "Changed",
        "Actualitzar README i .env.example",
    )


def test_classify_commit_message_ignores_noise_and_skip_ci() -> None:
    """Verifica que commits de CI, tests, merge o [skip ci] s'ometen del changelog."""
    assert classify_commit_message("chore(changelog): actualització automàtica [skip ci]") is None
    assert classify_commit_message("test(unit): afegir test de parser") is None
    assert classify_commit_message("Merge pull request #10 from feature/issue-10") is None
    assert classify_commit_message("") is None


def test_update_changelog_content_inserts_and_prevents_duplicates() -> None:
    """Comprova que update_changelog_content insereix entrades a [Unreleased] de forma idempotent."""
    base_changelog = (
        "# CHANGELOG\n\n"
        "## [Unreleased]\n\n"
        "---\n\n"
        "## [0.1.0] - 2026-03-01\n\n"
        "### Added\n"
        "- Versió inicial.\n"
    )
    commits = [
        "feat(menu): mostrar repositori actiu a la capçalera",
        "fix(parser): escapar cometes triples en JSON",
        "security(workspace): bloquejar rutes fora del workspace",
    ]
    grouped = group_commits_by_category(commits)
    updated = update_changelog_content(base_changelog, grouped)

    assert "### Added\n- **menu**: Mostrar repositori actiu a la capçalera" in updated
    assert "### Fixed\n- **parser**: Escapar cometes triples en JSON" in updated
    assert "### Security\n- **workspace**: Bloquejar rutes fora del workspace" in updated

    # Executar una segona vegada amb els mateixos commits no ha de duplicar res
    second_run = update_changelog_content(updated, grouped)
    assert second_run == updated


def test_release_unreleased_content_promotes_to_semver() -> None:
    """Comprova que release_unreleased_content mou les entrades d'[Unreleased] a una nova versió."""
    content = (
        "# CHANGELOG\n\n"
        "## [Unreleased]\n\n"
        "### Added\n"
        "- Nova funcionalitat multi-repositori\n\n"
        "---\n\n"
        "## [0.2.0] - 2026-10-25\n"
    )
    released = release_unreleased_content(content, "0.3.0", release_date="2026-10-27")

    assert "## [Unreleased]\n\n---\n\n## [0.3.0] - 2026-10-27\n\n### Added\n- Nova funcionalitat multi-repositori" in released

    with pytest.raises(ValueError, match="Semantic Versioning"):
        release_unreleased_content(content, "versio-invalida")


def test_update_changelog_file_and_cli_with_tmp_path(tmp_path: Path) -> None:
    """Verifica l'actualització del fitxer físic en un directori temporal (tmp_path)."""
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text(
        "# CHANGELOG\n\n## [Unreleased]\n\n---\n\n## [0.1.0] - 2026-03-01\n",
        encoding="utf-8",
    )

    changed = update_changelog_file(
        changelog_path=changelog_file,
        commits=["feat: suport per a múltiples repositoris"],
    )
    assert changed is True

    exit_code = main(
        [
            "--path",
            str(changelog_file),
            "--add",
            "security: validació d'entrades OWASP",
            "--release",
            "0.2.0",
        ]
    )
    assert exit_code == 0

    final_text = changelog_file.read_text(encoding="utf-8")
    assert "## [0.2.0]" in final_text
    assert "- Suport per a múltiples repositoris" in final_text
    assert "### Security\n- Validació d'entrades OWASP" in final_text

