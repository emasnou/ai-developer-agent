"""Tests unitaris per al motor d'actualització automàtica de documentació (`src/utils/doc_updater.py`)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.agents.developer_agent import DeveloperAgent
from src.utils.doc_updater import (
    extract_adr_metadata,
    generate_reference_markdown,
    inspect_python_module,
    main,
    scan_source_modules,
    sync_adr_index,
    update_all_documentation,
    validate_docstrings_and_types,
)


def test_validate_docstrings_and_types_real_src_is_100_percent_compliant() -> None:
    """Verifica que el 100% dels mòduls públics de `src/` compleixen docstrings i tipus de retorn."""
    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src"

    violations = validate_docstrings_and_types(src_dir=src_dir, root_dir=repo_root)

    assert not violations, (
        "S'han detectat fitxers a 'src/' que incompleixen la política de Docstrings (PEP 257) "
        "o Type Hints de retorn (PEP 484). IMPORTANT: Corregeix el fitxer de 'src/' indicat "
        "a continuació afegint-hi els docstrings o anotacions de retorn que hi falten "
        "(NO modifiquis src/utils/doc_updater.py):\n" + "\n".join(violations)
    )


def test_inspect_python_module_allows_init_without_docstring(tmp_path: Path) -> None:
    """Verifica que un fitxer `__init__.py` sense docstring no genera falsos positius."""
    src_dir = tmp_path / "src" / "utils"
    src_dir.mkdir(parents=True)
    init_file = src_dir / "__init__.py"
    init_file.write_text("", encoding="utf-8")

    info = inspect_python_module(init_file, tmp_path)

    assert info.module_path == "src.utils"
    assert info.violations == ()


def test_inspect_python_module_detects_missing_docstrings_and_return_types(
    tmp_path: Path,
) -> None:
    """Comprova que l'inspector AST detecta absència de docstrings i d'anotacions de retorn."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    bad_file = src_dir / "bad_module.py"
    bad_file.write_text(
        "class UndocumentedClass:\n"
        "    def public_method(self, x: int):\n"
        "        return x + 1\n\n"
        "def undocumented_func(a: str) -> str:\n"
        "    return a\n",
        encoding="utf-8",
    )

    info = inspect_python_module(bad_file, tmp_path)

    assert info.module_path == "src.bad_module"
    assert "UndocumentedClass" in info.classes
    assert "undocumented_func" in info.functions
    assert any("Manca docstring de mòdul" in v for v in info.violations)
    assert any("Manca docstring a la classe pública 'UndocumentedClass'" in v for v in info.violations)
    assert any("Manca docstring a la funció/mètode públic 'public_method'" in v for v in info.violations)
    assert any("Manca anotació de tipus de retorn (PEP 484) a 'public_method'" in v for v in info.violations)
    assert any("Manca docstring a la funció/mètode públic 'undocumented_func'" in v for v in info.violations)


def test_generate_reference_markdown_creates_table_and_mkdocstrings_blocks(
    tmp_path: Path,
) -> None:
    """Verifica que es genera la taula resum i els blocs `::: module` per a MkDocs."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('"""Paquet arrel."""\n', encoding="utf-8")
    (src_dir / "service.py").write_text(
        '"""Servei d\'exemple per a proves."""\n\n'
        "class DemoService:\n"
        '    """Classe de servei."""\n\n'
        "    def run(self) -> bool:\n"
        '        """Executa el servei."""\n'
        "        return True\n",
        encoding="utf-8",
    )

    modules = scan_source_modules(src_dir, tmp_path)
    markdown = generate_reference_markdown(modules)

    assert "# 📚 Referència Tècnica d'API (Auto-generada)" in markdown
    assert "| `src.service` |" in markdown
    assert "`DemoService`" in markdown
    assert "::: src.service" in markdown


def test_sync_adr_index_updates_readme_table_idempotently(tmp_path: Path) -> None:
    """Comprova que `sync_adr_index` actualitza la taula d'ADRs i és idempotent."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)

    readme = adr_dir / "README.md"
    readme.write_text(
        "# Registre d'ADRs\n\n"
        "## 📚 Índex d'ADRs del Projecte\n\n"
        "<!-- ADR-INDEX-START -->\n"
        "| ID | Títol |\n"
        "<!-- ADR-INDEX-END -->\n",
        encoding="utf-8",
    )
    adr_file = adr_dir / "0003-nova-arquitectura-cache.md"
    adr_file.write_text(
        "# ADR-0003: Nova Arquitectura de Cache Distribuïda\n\n"
        "| Camp | Valor |\n"
        "| :--- | :--- |\n"
        "| **ID d'ADR** | `ADR-0003` |\n"
        "| **Estat** | `Acceptat` |\n"
        "| **Data** | `2026-10-27` |\n"
        "| **Agent Autor** | `DeveloperAgent` |\n",
        encoding="utf-8",
    )

    meta = extract_adr_metadata(adr_file)
    assert meta is not None
    assert meta.adr_id == "0003"
    assert meta.title == "Nova Arquitectura de Cache Distribuïda"

    first_change = sync_adr_index(adr_dir)
    second_change = sync_adr_index(adr_dir)

    assert first_change is True
    assert second_change is False
    updated_readme = readme.read_text(encoding="utf-8")
    assert "**[ADR-0003](0003-nova-arquitectura-cache.md)**" in updated_readme
    assert "Nova Arquitectura de Cache Distribuïda" in updated_readme


def test_update_all_documentation_and_cli_check_mode(tmp_path: Path) -> None:
    """Verifica el flux complet d'`update_all_documentation` i les opcions CLI `--check` i `--validate-docstrings`."""
    src_dir = tmp_path / "src"
    adr_dir = tmp_path / "docs" / "adr"
    src_dir.mkdir(parents=True)
    adr_dir.mkdir(parents=True)

    (src_dir / "mod.py").write_text(
        '"""Mòdul validat."""\n\n'
        "def compute(val: int) -> int:\n"
        '    """Calcula el doble."""\n'
        "    return val * 2\n",
        encoding="utf-8",
    )
    (adr_dir / "README.md").write_text(
        "# ADRs\n\n## 📚 Índex d'ADRs del Projecte\n\n",
        encoding="utf-8",
    )

    # Abans de sincronitzar, el mode --check ha de detectar que falten actualitzacions (codi 1)
    assert main(["--root", str(tmp_path), "--check"]) == 1

    # Validació de docstrings ha de passar amb èxit (codi 0)
    assert main(["--root", str(tmp_path), "--validate-docstrings"]) == 0

    # Execució d'actualització automàtica des de CLI
    assert main(["--root", str(tmp_path)]) == 0
    assert (tmp_path / "docs" / "reference" / "index.md").is_file()

    # Un cop sincronitzat, --check ha de retornar 0
    assert main(["--root", str(tmp_path), "--check"]) == 0


def test_developer_agent_sync_workspace_documentation_adds_files_to_commit(
    tmp_path: Path,
) -> None:
    """Verifica que `DeveloperAgent._sync_workspace_documentation` afegeix la documentació regenerada al commit."""
    src_dir = tmp_path / "src"
    adr_dir = tmp_path / "docs" / "adr"
    src_dir.mkdir(parents=True)
    adr_dir.mkdir(parents=True)

    (src_dir / "feature.py").write_text(
        '"""Mòdul de nova funcionalitat."""\n\n'
        "def execute_feature() -> str:\n"
        '    """Executa la funcionalitat."""\n'
        '    return "ok"\n',
        encoding="utf-8",
    )
    (adr_dir / "README.md").write_text(
        "# ADRs\n\n## 📚 Índex d'ADRs del Projecte\n",
        encoding="utf-8",
    )

    agent = DeveloperAgent(
        llm_service=MagicMock(),
        github_service=MagicMock(),
        repo_name="owner/repo",
    )
    files_to_commit: list[dict[str, str]] = [
        {"path": "src/feature.py", "content": (src_dir / "feature.py").read_text(encoding="utf-8")}
    ]

    agent._sync_workspace_documentation(tmp_path, files_to_commit)

    committed_paths = [item["path"] for item in files_to_commit]
    assert "docs/reference/index.md" in committed_paths
    assert "docs/adr/README.md" in committed_paths


def test_developer_agent_preserves_local_files_and_extracts_pytest_failures(
    tmp_path: Path,
) -> None:
    """Verifica que `DeveloperAgent` no sobrescriu fitxers locals i conserva la secció FAILURES de PyTest."""
    mock_gh = MagicMock()
    mock_gh.get_repository_tree.return_value = ["src/utils/doc_updater.py", "src/new_remote.py"]
    mock_gh.get_file_content.side_effect = lambda path, ref="main": f"# Contingut remot de {path}\n"

    agent = DeveloperAgent(
        llm_service=MagicMock(),
        github_service=mock_gh,
        repo_name="owner/ai-developer-agent",
    )

    local_file = tmp_path / "src" / "utils" / "doc_updater.py"
    local_file.parent.mkdir(parents=True)
    local_file.write_text("# Contingut local corregit\n", encoding="utf-8")

    agent._download_branch_content(tmp_path, ref="main", overwrite_existing=False)

    assert local_file.read_text(encoding="utf-8") == "# Contingut local corregit\n"
    assert (tmp_path / "src" / "new_remote.py").read_text(encoding="utf-8") == (
        "# Contingut remot de src/new_remote.py\n"
    )

    test_file = tmp_path / "tests" / "unit" / "test_regression.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_reg() -> None:\n    assert True\n", encoding="utf-8")

    long_output = (
        "tests/unit/test_ok.py::test_pass PASSED\n" * 120
        + "=== FAILURES ===\n"
        + "___ test_reg ___\n"
        + "tests/unit/test_regression.py:2: AssertionError\n"
    )
    trimmed = DeveloperAgent._trim_pytest_output(long_output, max_chars=300)
    assert "=== FAILURES ===" in trimmed
    assert "AssertionError" in trimmed

    extra_ctx = DeveloperAgent._extract_failing_test_context(
        trimmed, tmp_path, [{"path": "src/other.py", "content": ""}]
    )
    assert "tests/unit/test_regression.py" in extra_ctx
    assert "def test_reg() -> None:" in extra_ctx


