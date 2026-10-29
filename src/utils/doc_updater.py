"""Motor d'actualització i verificació automàtica de la documentació tècnica (Docs-as-Code).

Aquest mòdul inspecciona l'arbre sintàctic (AST) del codi font (`src/`) i els registres
d'arquitectura (`docs/adr/`) per regenerar automàticament sense intervenció humana:
1. El portal de referència d'API (`docs/reference/index.md`) amb directives `mkdocstrings`.
2. L'índex de decisions d'arquitectura (`docs/adr/README.md`).
3. La validació estàtica de cobertura de docstrings i anotacions de retorn PEP 484.
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

_ADR_FILENAME_RE: re.Pattern[str] = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
_ADR_HEADING_RE: re.Pattern[str] = re.compile(r"^#\s+(?:ADR-\d{4}:\s*)?(.+)$", flags=re.MULTILINE)
_ADR_STATUS_RE: re.Pattern[str] = re.compile(r"\|\s*\*\*Estat\*\*\s*\|\s*`?([^|`\n]+)`?\s*\|")
_ADR_DATE_RE: re.Pattern[str] = re.compile(r"\|\s*\*\*Data\*\*\s*\|\s*`?([^|`\n]+)`?\s*\|")
_ADR_AUTHOR_RE: re.Pattern[str] = re.compile(
    r"\|\s*\*\*Agent Autor\*\*\s*\|\s*([^|\n]+)\|"
)
_ADR_TABLE_START: str = "<!-- ADR-INDEX-START -->"
_ADR_TABLE_END: str = "<!-- ADR-INDEX-END -->"


@dataclass(frozen=True)
class ModuleDocInfo:
    """Metadades documentals extretes de l'arbre AST d'un mòdul Python.

    Attributes:
        module_path: Nom canònic del mòdul en notació de punts (ex: `src.agents.base_agent`).
        relative_file: Ruta relativa del fitxer des de l'arrel del repositori.
        summary: Primera línia del docstring del mòdul.
        classes: Tupla amb els noms de les classes públiques definides al mòdul.
        functions: Tupla amb els noms de les funcions públiques de primer nivell.
        violations: Tupla d'incidències de documentació o tipat detectades a l'AST.
    """

    module_path: str
    relative_file: str
    summary: str
    classes: tuple[str, ...]
    functions: tuple[str, ...]
    violations: tuple[str, ...]


@dataclass(frozen=True)
class AdrEntry:
    """Metadades extretes d'un fitxer Architecture Decision Record (ADR).

    Attributes:
        adr_id: Identificador de 4 dígits (ex: `0001`).
        filename: Nom del fitxer Markdown dins de `docs/adr/`.
        title: Títol descriptiu de la decisió d'arquitectura.
        status: Estat actual de l'ADR (`Acceptat`, `Proposat`, `Plantilla`, etc.).
        date: Data de registre en format ISO (`YYYY-MM-DD`).
        author: Agent d'IA o equip autor de la decisió.
    """

    adr_id: str
    filename: str
    title: str
    status: str
    date: str
    author: str


def _check_callable_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    rel_path: str,
    parent_class: Optional[str] = None,
) -> list[str]:
    """Comprova que una funció o mètode tingui docstring (si és públic) i anotació de retorn.

    Args:
        node: Node AST de la funció o mètode a inspeccionar.
        rel_path: Ruta relativa del fitxer per als missatges de diagnòstic.
        parent_class: Nom de la classe contenidora si es tracta d'un mètode.

    Returns:
        list[str]: Llista d'incidències detectades (buida si compleix la normativa).
    """
    issues: list[str] = []
    context_suffix = f" (classe '{parent_class}')" if parent_class else ""
    is_public = not node.name.startswith("_") or node.name == "__init__"

    if is_public and not ast.get_docstring(node):
        issues.append(
            f"{rel_path}:{node.lineno} -> Manca docstring a la funció/mètode públic '{node.name}'{context_suffix}"
        )
    if node.returns is None:
        issues.append(
            f"{rel_path}:{node.lineno} -> Manca anotació de tipus de retorn (PEP 484) a '{node.name}'{context_suffix}"
        )
    return issues


def inspect_python_module(file_path: Path, root_dir: Path) -> ModuleDocInfo:
    """Analitza un fitxer Python amb `ast` per extreure'n l'estructura i validar-ne els docstrings.

    Args:
        file_path: Ruta del fitxer `.py` a inspeccionar.
        root_dir: Directori arrel del repositori per calcular rutes relatives.

    Returns:
        ModuleDocInfo: Informació documental i llista de violacions detectades.
    """
    rel_file = file_path.resolve().relative_to(root_dir.resolve()).as_posix()
    is_init_file = file_path.name == "__init__.py"
    module_name = rel_file[:-3].replace("/", ".")
    if module_name.endswith(".__init__"):
        module_name = module_name[: -len(".__init__")]

    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=rel_file)
    mod_doc = ast.get_docstring(tree) or ""
    default_summary = "Inicialització del paquet." if is_init_file else "Sense descripció de mòdul."
    summary = mod_doc.splitlines()[0].strip() if mod_doc else default_summary

    violations: list[str] = []
    if not mod_doc and not is_init_file:
        violations.append(f"{rel_file}:1 -> Manca docstring de mòdul")

    classes: list[str] = []
    functions: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)
            if not ast.get_docstring(node):
                violations.append(
                    f"{rel_file}:{node.lineno} -> Manca docstring a la classe pública '{node.name}'"
                )
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    violations.extend(_check_callable_node(sub, rel_file, parent_class=node.name))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                functions.append(node.name)
            violations.extend(_check_callable_node(node, rel_file))

    return ModuleDocInfo(
        module_path=module_name,
        relative_file=rel_file,
        summary=summary,
        classes=tuple(classes),
        functions=tuple(functions),
        violations=tuple(violations),
    )


def scan_source_modules(src_dir: Path, root_dir: Path) -> list[ModuleDocInfo]:
    """Escaneja tots els mòduls Python dins de `src/` de forma determinista.

    Args:
        src_dir: Ruta al directori `src/`.
        root_dir: Ruta a l'arrel del projecte.

    Returns:
        list[ModuleDocInfo]: Llista ordenada de metadades de tots els mòduls de `src/`.
    """
    if not src_dir.exists():
        return []
    py_files = sorted(src_dir.rglob("*.py"))
    return [inspect_python_module(f, root_dir) for f in py_files]


def validate_docstrings_and_types(src_dir: Path, root_dir: Path) -> list[str]:
    """Verifica que tots els mòduls, classes i funcions públiques de `src/` tinguin docstring i tipus.

    Args:
        src_dir: Ruta al directori `src/`.
        root_dir: Ruta a l'arrel del projecte.

    Returns:
        list[str]: Llista d'incompliments detectats (buida si el 100% del codi és conforme).
    """
    all_violations: list[str] = []
    for mod in scan_source_modules(src_dir, root_dir):
        all_violations.extend(mod.violations)
    return all_violations


def generate_reference_markdown(modules: Sequence[ModuleDocInfo]) -> str:
    """Genera el contingut Markdown de `docs/reference/index.md` per a MkDocs i consulta directa.

    Args:
        modules: Seqüència de mòduls analitzats de `src/`.

    Returns:
        str: Document Markdown complet amb taula resum i directives `mkdocstrings`.
    """
    non_init_modules = [m for m in modules if not m.relative_file.endswith("__init__.py")]
    lines: list[str] = [
        "# 📚 Referència Tècnica d'API (Auto-generada)",
        "",
        "> **Nota d'automatització (Docs-as-Code):** Aquest document es genera i s'actualitza",
        "> automàticament a partir de l'arbre sintàctic (AST) i dels docstrings Google Style",
        "> del codi font mitjançant `python -m src.utils.doc_updater`.",
        "",
        "## 🗺️ Mapa de Mòduls del Sistema (`src/`)",
        "",
        "| Mòdul | Fitxer | Responsabilitat Principal | Elements Públics |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for mod in non_init_modules:
        symbols = [*mod.classes, *mod.functions]
        symbols_str = ", ".join(f"`{s}`" for s in symbols) if symbols else "*(Mòdul de constants)*"
        lines.append(
            f"| `{mod.module_path}` | [`{mod.relative_file}`](../../{mod.relative_file}) "
            f"| {mod.summary} | {symbols_str} |"
        )

    lines.extend(["", "---", "", "## 🔍 Especificació Detallada de Mòduls (mkdocstrings)", ""])
    for mod in non_init_modules:
        lines.extend([
            f"### `{mod.module_path}`",
            "",
            f"- **Fitxer font:** [`{mod.relative_file}`](../../{mod.relative_file})",
            f"- **Resum:** {mod.summary}",
            "",
            f"::: {mod.module_path}",
            "",
        ])

    return "\n".join(lines).rstrip() + "\n"


def extract_adr_metadata(adr_file: Path) -> Optional[AdrEntry]:
    """Extreu l'identificador, títol, estat, data i autor d'un fitxer ADR en Markdown.

    Args:
        adr_file: Fitxer `.md` situat a `docs/adr/`.

    Returns:
        Optional[AdrEntry]: Metadades extretes o `None` si el fitxer no segueix el patró `NNNN-*.md`.
    """
    match_name = _ADR_FILENAME_RE.match(adr_file.name)
    if not match_name:
        return None

    adr_id = match_name.group(1)
    content = adr_file.read_text(encoding="utf-8")

    if adr_id == "0000":
        return AdrEntry(
            adr_id="0000",
            filename=adr_file.name,
            title="**Plantilla Oficial d'ADR per a Agents d'IA i Enginyers**",
            status="Plantilla",
            date="2026-10-27",
            author="Arquitectura / Docs-as-Code",
        )

    heading_match = _ADR_HEADING_RE.search(content)
    title = heading_match.group(1).strip() if heading_match else adr_file.stem
    status_match = _ADR_STATUS_RE.search(content)
    status = status_match.group(1).strip() if status_match else "Acceptat"
    date_match = _ADR_DATE_RE.search(content)
    date_val = date_match.group(1).strip() if date_match else "N/A"
    author_match = _ADR_AUTHOR_RE.search(content)
    author = author_match.group(1).strip() if author_match else "`DeveloperAgent`"

    return AdrEntry(
        adr_id=adr_id,
        filename=adr_file.name,
        title=title,
        status=status,
        date=date_val,
        author=author,
    )


def build_adr_index_table(adr_dir: Path) -> str:
    """Construeix la taula Markdown d'índex d'ADRs escanejant tots els fitxers de `docs/adr/`.

    Args:
        adr_dir: Ruta al directori `docs/adr/`.

    Returns:
        str: Taula Markdown delimitada per marcadors d'actualització automàtica.
    """
    entries: list[AdrEntry] = []
    if adr_dir.exists():
        for file_path in sorted(adr_dir.glob("*.md")):
            entry = extract_adr_metadata(file_path)
            if entry is not None:
                entries.append(entry)

    rows: list[str] = [
        _ADR_TABLE_START,
        "| ID | Títol de la Decisió | Estat | Data | Autor / Agent IA |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for item in entries:
        rows.append(
            f"| **[ADR-{item.adr_id}]({item.filename})** | {item.title} "
            f"| `{item.status}` | {item.date} | {item.author} |"
        )
    rows.append(_ADR_TABLE_END)
    return "\n".join(rows)


def sync_adr_index(adr_dir: Path) -> bool:
    """Sincronitza automàticament la taula d'ADRs dins de `docs/adr/README.md`.

    Args:
        adr_dir: Ruta al directori `docs/adr/`.

    Returns:
        bool: `True` si el fitxer `docs/adr/README.md` s'ha modificat, `False` si ja estava al dia.
    """
    readme_path = adr_dir / "README.md"
    if not readme_path.exists():
        return False

    current = readme_path.read_text(encoding="utf-8")
    new_table = build_adr_index_table(adr_dir)

    if _ADR_TABLE_START in current and _ADR_TABLE_END in current:
        pattern = re.compile(
            re.escape(_ADR_TABLE_START) + r".*?" + re.escape(_ADR_TABLE_END),
            flags=re.DOTALL,
        )
        updated = pattern.sub(new_table, current)
    elif "## 📚 Índex d'ADRs del Projecte" in current:
        prefix = current.split("## 📚 Índex d'ADRs del Projecte")[0]
        updated = f"{prefix}## 📚 Índex d'ADRs del Projecte\n\n{new_table}\n"
    else:
        updated = f"{current.rstrip()}\n\n## 📚 Índex d'ADRs del Projecte\n\n{new_table}\n"

    if updated != current:
        readme_path.write_text(updated, encoding="utf-8")
        return True
    return False


def update_all_documentation(root_dir: Path = Path(".")) -> list[str]:
    """Executa la sincronització automàtica de la referència d'API i de l'índex d'ADRs.

    Args:
        root_dir: Directori arrel del repositori o del workspace a sincronitzar.

    Returns:
        list[str]: Llista de rutes relatives dels fitxers de documentació actualitzats.
    """
    resolved_root = root_dir.resolve()
    src_dir = resolved_root / "src"
    ref_file = resolved_root / "docs" / "reference" / "index.md"
    adr_dir = resolved_root / "docs" / "adr"

    updated_files: list[str] = []
    if src_dir.exists():
        modules = scan_source_modules(src_dir, resolved_root)
        new_ref_content = generate_reference_markdown(modules)
        old_ref_content = ref_file.read_text(encoding="utf-8") if ref_file.exists() else ""
        if new_ref_content != old_ref_content:
            ref_file.parent.mkdir(parents=True, exist_ok=True)
            ref_file.write_text(new_ref_content, encoding="utf-8")
            updated_files.append("docs/reference/index.md")

    if sync_adr_index(adr_dir):
        updated_files.append("docs/adr/README.md")

    hooks_dir = resolved_root / ".git" / "hooks"
    for hook_name in ("pre-commit", "post-commit"):
        hook_path = hooks_dir / hook_name
        if hook_path.is_file():
            try:
                hook_path.chmod(0o755)
            except OSError:
                pass

    return updated_files


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Punt d'entrada CLI per actualitzar i verificar la documentació automàticament.

    Args:
        argv: Llista opcional d'arguments de línia de comandes.

    Returns:
        int: Codi de sortida (`0` si tot és correcte, `1` si hi ha errors de validació).
    """
    parser = argparse.ArgumentParser(
        description="Sincronitza i valida automàticament la documentació tècnica (Docs-as-Code)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Ruta a l'arrel del projecte (per defecte: directori actual).",
    )
    parser.add_argument(
        "--validate-docstrings",
        action="store_true",
        help="Verifica que tots els mòduls, classes i funcions públiques de src/ tinguin docstring i tipus.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Comprova si la documentació generada està sincronitzada sense sobrescriure fitxers.",
    )
    args = parser.parse_args(argv)
    resolved_root = args.root.resolve()

    if args.validate_docstrings:
        violations = validate_docstrings_and_types(resolved_root / "src", resolved_root)
        if violations:
            print("❌ S'han detectat incompliments de Docstrings / Type Hints a src/:")
            for v in violations:
                print(f"  - {v}")
            return 1
        print("✅ Tots els mòduls, classes i funcions de src/ compleixen Docstrings i Type Hints.")

    if args.check:
        modules = scan_source_modules(resolved_root / "src", resolved_root)
        expected_ref = generate_reference_markdown(modules)
        ref_file = resolved_root / "docs" / "reference" / "index.md"
        current_ref = ref_file.read_text(encoding="utf-8") if ref_file.exists() else ""
        if expected_ref != current_ref:
            print("⚠️ docs/reference/index.md no està sincronitzat amb el codi font.")
            return 1
        print("✅ La documentació de referència està sincronitzada.")
        return 0

    updated_files = update_all_documentation(resolved_root)
    if updated_files:
        print(
            f"📚 Documentació sincronitzada automàticament ({', '.join(updated_files)})."
        )
    else:
        print("ℹ️ La documentació tècnica ja es trobava completament actualitzada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

