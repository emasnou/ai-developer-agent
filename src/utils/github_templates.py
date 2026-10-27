"""Utilitats per a la càrrega i renderització de les plantilles de GitHub (`.github/`).

Aquest mòdul garanteix que tots els agents del cicle de desenvolupament (`AnalystAgent`,
`DeveloperAgent` i `CodeReviewAgent`) utilitzin les plantilles oficials d'Issues i Pull Requests
definides a `.github/ISSUE_TEMPLATE/` i `.github/pull_request_template.md`, prioritzant les
plantilles del repositori actiu sincronitzat al workspace quan estiguin disponibles.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_FRONTMATTER_RE: re.Pattern[str] = re.compile(r"\A---\s*\n.*?\n---\s*\n*", flags=re.DOTALL)

PR_TEMPLATE_REL_PATH: str = ".github/pull_request_template.md"
FEATURE_ISSUE_TEMPLATE_REL_PATH: str = ".github/ISSUE_TEMPLATE/feature_request.md"
IMPROVEMENT_ISSUE_TEMPLATE_REL_PATH: str = ".github/ISSUE_TEMPLATE/improvement_recommendation.md"
BUG_ISSUE_TEMPLATE_REL_PATH: str = ".github/ISSUE_TEMPLATE/bug_report.md"


def strip_yaml_frontmatter(template_text: str) -> str:
    """Elimina l'encapçalament YAML (`--- ... ---`) propi de les plantilles d'Issues de GitHub.

    Args:
        template_text: Contingut complet del fitxer de plantilla Markdown.

    Returns:
        str: Cos Markdown net sense metadades YAML inicials.
    """
    return _FRONTMATTER_RE.sub("", template_text.lstrip()).strip()


def load_github_template(
    relative_path: str,
    workspace_dir: Optional[Path] = None,
    fallback: str = "",
    strip_frontmatter: bool = True,
) -> str:
    """Carrega una plantilla de `.github/` prioritzant el workspace actiu i l'arrel del projecte.

    Args:
        relative_path: Ruta relativa de la plantilla (ex: `.github/pull_request_template.md`).
        workspace_dir: Directori opcional del workspace per prioritzar la plantilla del repo actiu.
        fallback: Contingut de reserva si el fitxer de plantilla no es troba.
        strip_frontmatter: Si és True, elimina el bloc YAML inicial de la plantilla.

    Returns:
        str: Contingut de la plantilla carregada (o `fallback` si no existeix).
    """
    candidates: list[Path] = []
    if workspace_dir is not None:
        candidates.append(workspace_dir / relative_path)
    candidates.append(Path(relative_path))
    # Afegim l'arrel física del paquet perquè els tests amb monkeypatch.chdir(tmp_path)
    # puguin resoldre les plantilles canòniques sense haver de duplicar .github/ a cada test
    candidates.append(_REPO_ROOT / relative_path)

    for candidate in candidates:
        if candidate.is_file():
            raw_content = candidate.read_text(encoding="utf-8")
            return strip_yaml_frontmatter(raw_content) if strip_frontmatter else raw_content.strip()

    return strip_yaml_frontmatter(fallback) if (strip_frontmatter and fallback) else fallback


def render_pull_request_body(
    issue_number: int,
    issue_title: str,
    branch_name: str,
    files_to_commit: list[dict[str, str]],
    attempt: int,
    summary: str = "",
    workspace_dir: Optional[Path] = None,
    template_path: Optional[Path] = None,
) -> str:
    """Renderitza el cos d'una Pull Request utilitzant `.github/pull_request_template.md`.

    Args:
        issue_number: Número de la Issue de GitHub que es resol.
        issue_title: Títol de la Issue resolta.
        branch_name: Nom de la branca d'origen amb els canvis.
        files_to_commit: Llista de diccionaris amb les rutes (`path`) dels fitxers modificats.
        attempt: Nombre d'intents de PyTest necessaris per validar la solució.
        summary: Resum executiu dels canvis generat pel DeveloperAgent.
        workspace_dir: Ruta opcional del workspace per usar la plantilla del repositori actiu.
        template_path: Ruta explícita opcional a una plantilla de PR personalitzada.

    Returns:
        str: Cos de la Pull Request en format Markdown llest per publicar a GitHub.
    """
    rel_path = str(template_path) if template_path is not None else PR_TEMPLATE_REL_PATH
    template = load_github_template(
        relative_path=rel_path,
        workspace_dir=workspace_dir,
        strip_frontmatter=True,
    )

    files_summary = (
        "\n".join(f"- `{item['path']}`" for item in files_to_commit)
        if files_to_commit
        else "- Cap fitxer especificat"
    )
    resolved_summary = (
        f"Aquesta Pull Request ha estat generada automàticament per l'**Agent Desenvolupador "
        f"(Workspace Sincronitzat)**.\n\n** síntesi tècnica:** {summary}"
        if summary
        else "Aquesta Pull Request ha estat generada automàticament per l'**Agent Desenvolupador**."
    )
    tests_status = f"Passats satisfactòriament en {attempt} intent/s"

    if not template:
        return (
            f"{resolved_summary}\n\n"
            f"- **Issue resolta:** Closes #{issue_number} ({issue_title})\n"
            f"- **Branca origen:** `{branch_name}`\n"
            f"- **Fitxers modificats/creats:**\n{files_summary}\n"
            f"- **Tests executats:** {tests_status}"
        )

    replacements: dict[str, str] = {
        "{{SUMMARY}}": resolved_summary,
        "{{ISSUE_NUMBER}}": str(issue_number),
        "{{ISSUE_TITLE}}": issue_title,
        "{{BRANCH_NAME}}": branch_name,
        "{{FILES_SUMMARY}}": files_summary,
        "{{TESTS_STATUS}}": tests_status,
        "{{ATTEMPTS}}": str(attempt),
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def render_improvement_issue_body(
    description: str,
    code_filename: str,
    test_filename: str,
    pr_number: Optional[int] = None,
    workspace_dir: Optional[Path] = None,
    template_path: Optional[Path] = None,
) -> str:
    """Formata el cos d'una Issue de millora contínua amb la plantilla `.github/ISSUE_TEMPLATE/`.

    Args:
        description: Descripció o proposta retornada pel CodeReviewAgent.
        code_filename: Fitxer de codi principal afectat per la recomanació.
        test_filename: Fitxer de tests unitaris associat.
        pr_number: Número opcional de la Pull Request d'on prové la recomanació.
        workspace_dir: Ruta opcional del workspace actiu.
        template_path: Ruta explícita opcional a la plantilla d'Issue de millora.

    Returns:
        str: Cos de la Issue en format Markdown estructurat segons la plantilla.
    """
    rel_path = (
        str(template_path) if template_path is not None else IMPROVEMENT_ISSUE_TEMPLATE_REL_PATH
    )
    template = load_github_template(
        relative_path=rel_path,
        workspace_dir=workspace_dir,
        strip_frontmatter=True,
    )
    pr_ref = f"PR #{pr_number}" if pr_number is not None else "Auditoria de Code Review"
    cleaned_desc = description.strip()

    if not template:
        return cleaned_desc

    # Si l'LLM ja ha retornat el text dividit entre Context i Proposta o un text únic,
    # separem les seccions si existeixen per evitar duplicar encapçalaments a la plantilla
    context_text = cleaned_desc
    proposal_text = (
        f"Refactoritzar `{code_filename}` aplicant la millora descrita i "
        f"validar el nou comportament amb proves unitàries a `{test_filename}`."
    )
    if "**Proposta d'implementació:**" in cleaned_desc:
        parts = cleaned_desc.split("**Proposta d'implementació:**", maxsplit=1)
        context_text = parts[0].replace("## 💡 Millora Recomanada", "").strip()
        proposal_text = parts[1].strip() or proposal_text

    replacements: dict[str, str] = {
        "{{PR_REFERENCE}}": pr_ref,
        "{{CODE_FILENAME}}": code_filename,
        "{{TEST_FILENAME}}": test_filename,
        "{{CONTEXT}}": context_text,
        "{{PROPOSAL}}": proposal_text,
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered

