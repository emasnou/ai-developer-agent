"""Mòdul per a la gestió, numeració seqüencial i materialització d'ADRs.

Aquest mòdul proporciona la lògica per generar noms de fitxers segurs (mitigant Path Traversal),
calcular la numeració seqüencial correlativa de decisions d'arquitectura i renderitzar
registres ADR vàlids segons la plantilla oficial de Docs-as-Code.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from src.schemas.agent_schemas import ArchitectureDecisionRecord

_ADR_FILE_PATTERN: re.Pattern[str] = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
_INVALID_CHARS_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9-]+")


def slugify_title(title: str, max_length: int = 50) -> str:
    """Sanititza i normalitza el títol per al nom de fitxer de l'ADR.

    Elimina accents, caràcters especials i seqüències potencialment perilloses
    (OWASP A01/A04) per garantir un nom segur i compatible amb el sistema de fitxers.

    Args:
        title: Títol descriptiu de la decisió d'arquitectura.
        max_length: Longitud màxima permesa per a l'slug generat.

    Returns:
        str: Cadena normalitzada en minúscules amb guions com a separadors.
    """
    normalized = unicodedata.normalize("NFKD", title)
    ascii_clean = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _INVALID_CHARS_PATTERN.sub("-", ascii_clean).strip("-")
    if not slug:
        slug = "decisio-arquitectura"
    return slug[:max_length].rstrip("-")


def get_next_adr_id(adr_dir: Path) -> str:
    """Calcula el següent identificador seqüencial de 4 dígits per a un nou ADR.

    Inspecciona els fitxers existents a `docs/adr/`, ignora la plantilla base `0000`
    i calcula el valor màxim incrementat en una unitat sense col·lisions.

    Args:
        adr_dir: Ruta al directori on s'ubiquen els fitxers ADR.

    Returns:
        str: Cadena de 4 dígits amb zeros a l'esquerra (ex: `'0003'`).
    """
    if not adr_dir.exists():
        return "0001"

    highest_id = 0
    for file_path in adr_dir.glob("*.md"):
        match = _ADR_FILE_PATTERN.match(file_path.name)
        if match:
            current_id = int(match.group(1))
            if current_id > highest_id and current_id != 0:
                highest_id = current_id

    next_id = highest_id + 1
    return f"{next_id:04d}"


def build_adr_filename(next_id: str, title: str) -> str:
    """Genera el nom de fitxer per a un nou registre d'arquitectura.

    Args:
        next_id: Identificador de 4 dígits calculat (ex: `'0003'`).
        title: Títol o propòsit de la decisió d'arquitectura.

    Returns:
        str: Nom del fitxer formatat (ex: `'0003-eleccio-persistencia.md'`).
    """
    clean_slug = slugify_title(title)
    return f"{next_id}-{clean_slug}.md"


def materialize_adr_file(
    adr_data: ArchitectureDecisionRecord | dict[str, Any],
    adr_dir: Path,
) -> Path:
    """Escriu el fitxer ADR al directori corresponent prevenint Path Traversal.

    Args:
        adr_data: Objecte o diccionari amb les dades de l'Architecture Decision Record.
        adr_dir: Directori destí (normalment `docs/adr`).

    Returns:
        Path: Ruta absoluta del fitxer ADR creat.

    Raises:
        ValueError: Si la ruta resultant intenta sortir del directori permès.
    """
    adr_dir.mkdir(parents=True, exist_ok=True)
    record = (
        adr_data
        if isinstance(adr_data, ArchitectureDecisionRecord)
        else ArchitectureDecisionRecord(**adr_data)
    )

    next_numeric = get_next_adr_id(adr_dir)
    expected_id = f"ADR-{next_numeric}"
    # Usem model_copy per preservar la immutabilitat si cal i assignar el número correlatiu
    record = record.model_copy(update={"adr_id": expected_id})

    filename = build_adr_filename(next_numeric, record.title)
    target_path = (adr_dir / filename).resolve()

    # Verifiquem que cap atac de Path Traversal pugui escapar del directori adr (OWASP A01)
    if not target_path.is_relative_to(adr_dir.resolve()):
        raise ValueError(f"Ruta ADR no permesa fora del directori: {filename}")

    target_path.write_text(record.to_markdown(), encoding="utf-8")
    return target_path
