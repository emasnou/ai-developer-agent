"""Mòdul d'automatització i validació per mantenir actualitzat el fitxer CHANGELOG.md.

Segueix l'estàndard Keep a Changelog i Semantic Versioning (MAJOR.MINOR.PATCH),
classificant automàticament els missatges de commit (Conventional Commits) en les
categories `Added`, `Changed`, `Fixed` i `Security`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

CHANGELOG_CATEGORIES: tuple[str, ...] = ("Added", "Changed", "Fixed", "Security")

_COMMIT_TYPE_MAP: dict[str, str] = {
    "feat": "Added",
    "add": "Added",
    "added": "Added",
    "change": "Changed",
    "changed": "Changed",
    "refactor": "Changed",
    "perf": "Changed",
    "docs": "Changed",
    "fix": "Fixed",
    "bugfix": "Fixed",
    "hotfix": "Fixed",
    "fixed": "Fixed",
    "security": "Security",
    "sec": "Security",
}

_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<desc>.+)$"
)
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def classify_commit_message(message: str) -> Optional[tuple[str, str]]:
    """Classifica un missatge de commit en una categoria de Keep a Changelog.

    Args:
        message: Primera línia del missatge de commit en format Conventional Commits.

    Returns:
        Optional[tuple[str, str]]: Tupla `(categoria, entrada_formatada)` on categoria és
        una de `('Added', 'Changed', 'Fixed', 'Security')`, o `None` si el commit s'ha d'ometre.
    """
    first_line = message.strip().splitlines()[0].strip() if message.strip() else ""
    if not first_line or "[skip ci]" in first_line.lower():
        return None

    match = _CONVENTIONAL_COMMIT_RE.match(first_line)
    if not match:
        return None

    commit_type = match.group("type").lower()
    scope = (match.group("scope") or "").strip()
    description = match.group("desc").strip()

    if commit_type == "chore" and scope.lower() == "changelog":
        return None

    category = _COMMIT_TYPE_MAP.get(commit_type)
    if category is None or not description:
        return None

    formatted_desc = description[0].upper() + description[1:]
    entry = f"**{scope}**: {formatted_desc}" if scope else formatted_desc
    return category, entry


def group_commits_by_category(messages: list[str]) -> dict[str, list[str]]:
    """Agrupa una llista de missatges de commit en les categories de Keep a Changelog.

    Args:
        messages: Llista de missatges de commit a processar.

    Returns:
        dict[str, list[str]]: Diccionari amb claus `'Added'`, `'Changed'`, `'Fixed'`, `'Security'`.
    """
    grouped: dict[str, list[str]] = {cat: [] for cat in CHANGELOG_CATEGORIES}
    for msg in messages:
        classified = classify_commit_message(msg)
        if classified is None:
            continue
        category, entry = classified
        if entry not in grouped[category]:
            grouped[category].append(entry)
    return grouped


def _ensure_unreleased_header(content: str) -> str:
    """Garanteix que el contingut del CHANGELOG tingui la secció `## [Unreleased]`.

    Args:
        content: Contingut complet actual del fitxer `CHANGELOG.md`.

    Returns:
        str: Contingut amb la capçalera `## [Unreleased]` present.
    """
    if "## [Unreleased]" in content:
        return content

    first_release_match = re.search(r"^## \[\d+\.\d+\.\d+\]", content, flags=re.MULTILINE)
    if first_release_match:
        idx = first_release_match.start()
        return f"{content[:idx]}## [Unreleased]\n\n---\n\n{content[idx:]}"

    return f"{content.rstrip()}\n\n## [Unreleased]\n"


def _parse_unreleased_sections(unreleased_body: str) -> dict[str, list[str]]:
    """Extreu els elements existents dins del bloc `## [Unreleased]` per categoria.

    Args:
        unreleased_body: Text comprès entre `## [Unreleased]` i la següent versió.

    Returns:
        dict[str, list[str]]: Llista d'entrades per cada categoria estàndard.
    """
    sections: dict[str, list[str]] = {cat: [] for cat in CHANGELOG_CATEGORIES}
    current_cat: Optional[str] = None

    for raw_line in unreleased_body.splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            header_name = line[4:].strip()
            current_cat = header_name if header_name in sections else None
        elif line.startswith("- ") and current_cat is not None:
            sections[current_cat].append(line[2:].strip())

    return sections


def _render_category_sections(sections: dict[str, list[str]]) -> str:
    """Renderitza les categories no buides en format Markdown Keep a Changelog.

    Args:
        sections: Diccionari de categories amb les seves llistes d'entrades.

    Returns:
        str: Bloc Markdown formatat amb `### Added`, `### Changed`, `### Fixed`, `### Security`.
    """
    blocks: list[str] = []
    for category in CHANGELOG_CATEGORIES:
        items = sections.get(category, [])
        if not items:
            continue
        bullets = "\n".join(f"- {item}" for item in items)
        blocks.append(f"### {category}\n{bullets}")
    return "\n\n".join(blocks)


def update_changelog_content(content: str, entries_by_category: dict[str, list[str]]) -> str:
    """Actualitza el contingut de `CHANGELOG.md` afegint noves entrades sense duplicats.

    Args:
        content: Contingut actual del fitxer `CHANGELOG.md`.
        entries_by_category: Noves entrades agrupades per `Added`, `Changed`, `Fixed`, `Security`.

    Returns:
        str: Contingut actualitzat amb les noves entrades sota `## [Unreleased]`.
    """
    normalized = _ensure_unreleased_header(content)
    pattern = re.compile(
        r"(^## \[Unreleased\]\s*\n)(?P<body>.*?)(?=^---\s*\n^## \[|^## \[|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(normalized)
    if not match:
        return normalized

    existing_sections = _parse_unreleased_sections(match.group("body"))
    added_any = False

    for category in CHANGELOG_CATEGORIES:
        for entry in entries_by_category.get(category, []):
            if entry not in normalized and entry not in existing_sections[category]:
                existing_sections[category].append(entry)
                added_any = True

    if not added_any:
        return content

    rendered_body = _render_category_sections(existing_sections)
    replacement = f"## [Unreleased]\n\n{rendered_body}\n\n"
    return normalized[: match.start()] + replacement + normalized[match.end() :]


def release_unreleased_content(
    content: str, version: str, release_date: Optional[str] = None
) -> str:
    """Promociona el contingut actual de `## [Unreleased]` a una nova versió SemVer.

    Args:
        content: Contingut actual de `CHANGELOG.md`.
        version: Nova versió en format SemVer `MAJOR.MINOR.PATCH` (ex: `'0.4.0'`).
        release_date: Data en format ISO `YYYY-MM-DD` (per defecte la data d'avui).

    Returns:
        str: Contingut de `CHANGELOG.md` amb la nova secció de versió creada.

    Raises:
        ValueError: Si la versió no compleix el format `MAJOR.MINOR.PATCH`.
    """
    clean_version = version.lstrip("v").strip()
    if not _SEMVER_RE.match(clean_version):
        raise ValueError(
            f"La versió '{version}' no compleix Semantic Versioning (MAJOR.MINOR.PATCH)."
        )

    target_date = release_date or date.today().isoformat()
    normalized = _ensure_unreleased_header(content)
    pattern = re.compile(
        r"(^## \[Unreleased\]\s*\n)(?P<body>.*?)(?=^---\s*\n^## \[|^## \[|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(normalized)
    if not match:
        return normalized

    sections = _parse_unreleased_sections(match.group("body"))
    rendered = _render_category_sections(sections)
    if not rendered:
        return normalized

    new_section = f"## [Unreleased]\n\n---\n\n## [{clean_version}] - {target_date}\n\n{rendered}\n\n"
    return normalized[: match.start()] + new_section + normalized[match.end() :]


def get_recent_git_commits(repo_dir: Path = Path("."), max_count: int = 20) -> list[str]:
    """Obté els missatges de commit recents des de l'últim tag o els últims `max_count` commits.

    Args:
        repo_dir: Ruta del repositori Git local.
        max_count: Nombre màxim de commits a consultar si no hi ha tags.

    Returns:
        list[str]: Llista de línies de títol dels commits (del més antic al més recent).
    """
    try:
        tag_res = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        rev_range = (
            f"{tag_res.stdout.strip()}..HEAD"
            if tag_res.returncode == 0 and tag_res.stdout.strip()
            else f"-n {max_count}"
        )
        cmd = ["git", "log", "--pretty=format:%s", *rev_range.split()]
        log_res = subprocess.run(
            cmd,
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if log_res.returncode != 0 or not log_res.stdout.strip():
            return []
        commits = [line.strip() for line in log_res.stdout.splitlines() if line.strip()]
        commits.reverse()
        return commits
    except Exception:
        return []


def update_changelog_file(
    changelog_path: Path = Path("CHANGELOG.md"),
    commits: Optional[list[str]] = None,
    release_version: Optional[str] = None,
) -> bool:
    """Actualitza el fitxer `CHANGELOG.md` a disc amb nous commits i/o una nova versió.

    Args:
        changelog_path: Ruta al fitxer `CHANGELOG.md`.
        commits: Llista opcional de missatges de commit; si és `None`, es llegeixen de Git.
        release_version: Versió SemVer opcional per promocionar `[Unreleased]`.

    Returns:
        bool: `True` si el fitxer `CHANGELOG.md` s'ha modificat, `False` si ja estava al dia.
    """
    if not changelog_path.exists():
        return False

    original = changelog_path.read_text(encoding="utf-8")
    source_commits = commits if commits is not None else get_recent_git_commits(changelog_path.parent)
    grouped = group_commits_by_category(source_commits)
    updated = update_changelog_content(original, grouped)

    if release_version:
        updated = release_unreleased_content(updated, release_version)

    if updated != original:
        changelog_path.write_text(updated, encoding="utf-8")
        return True
    return False


def main(argv: Optional[list[str]] = None) -> int:
    """Punt d'entrada CLI per a l'actualització automàtica de `CHANGELOG.md`.

    Args:
        argv: Llista opcional d'arguments de línia d'ordres.

    Returns:
        int: Codi de sortida (`0` en cas d'èxit).
    """
    parser = argparse.ArgumentParser(
        description="Actualitza automàticament CHANGELOG.md seguint Keep a Changelog i SemVer."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Ruta al fitxer CHANGELOG.md (per defecte: CHANGELOG.md).",
    )
    parser.add_argument(
        "--add",
        action="append",
        dest="commits",
        help="Missatge en format Conventional Commits per afegir (pot repetir-se).",
    )
    parser.add_argument(
        "--release",
        type=str,
        default=None,
        help="Promociona [Unreleased] a la versió SemVer indicada (ex: 0.4.0).",
    )
    args = parser.parse_args(argv)

    changed = update_changelog_file(
        changelog_path=args.path,
        commits=args.commits,
        release_version=args.release,
    )
    if changed:
        print(f"✅ Fitxer '{args.path}' actualitzat correctament.")
    else:
        print(f"ℹ️ El fitxer '{args.path}' ja està actualitzat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

