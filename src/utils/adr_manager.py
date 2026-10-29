"""Mòdul per a la gestió, numeració seqüencial i materialització d'ADRs.

Aquest mòdul proporciona la lògica per generar noms de fitxers segurs (mitigant Path Traversal),
calcular la numeració seqüencial correlativa de decisions d'arquitectura de forma estrictament
numèrica, i renderitzar registres ADR vàlids sota un bloqueig atòmic per prevenir condicions de cursa.
"""

from __future__ import annotations

import contextlib
import re
import threading
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from src.schemas.agent_schemas import ArchitectureDecisionRecord

_ADR_FILE_PATTERN: re.Pattern[str] = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
_INVALID_CHARS_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9-]+")
_THREAD_LOCK: threading.RLock = threading.RLock()


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


@contextlib.contextmanager
def adr_lock(adr_dir: Path) -> Iterator[None]:
    """Bloqueig atòmic (inter-procés i multi-fil) per a operacions concurrents sobre ADRs.

    Args:
        adr_dir: Ruta al directori on s'ubiquen els fitxers ADR.

    Yields:
        None: Quan el bloqueig s'ha adquirit satisfactòriament.
    """
    adr_dir.mkdir(parents=True, exist_ok=True)
    lock_file_path = adr_dir / ".adr.lock"

    with _THREAD_LOCK:
        if fcntl is not None:
            with open(lock_file_path, "a+", encoding="utf-8") as lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    yield
                finally:
                    try:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
        else:
            yield


def _calculate_next_id_unlocked(adr_dir: Path) -> str:
    """Calcula el següent identificador numèric sense adquirir locks interns.

    Args:
        adr_dir: Ruta al directori on s'ubiquen els fitxers ADR.

    Returns:
        str: Cadena de 4 dígits amb zeros a l'esquerra.
    """
    if not adr_dir.exists():
        return "0001"

    numeric_ids: list[int] = []
    for file_path in adr_dir.glob("*.md"):
        match = _ADR_FILE_PATTERN.match(file_path.name)
        if match:
            current_id = int(match.group(1))
            if current_id > 0:
                numeric_ids.append(current_id)

    if not numeric_ids:
        return "0001"

    # Ordenació estrictament numèrica dels identificadors existents
    numeric_ids.sort()
    next_id = numeric_ids[-1] + 1
    return f"{next_id:04d}"


def get_next_adr_id(adr_dir: Path) -> str:
    """Calcula el següent identificador seqüencial de 4 dígits per a un nou ADR.

    Inspecciona els fitxers existents a `docs/adr/`, ignora la plantilla base `0000`,
    aplica ordenació estrictament numèrica i calcula el valor màxim incrementat en
    una unitat sota protecció de bloqueig per prevenir condicions de cursa.

    Args:
        adr_dir: Ruta al directori on s'ubiquen els fitxers ADR.

    Returns:
        str: Cadena de 4 dígits amb zeros a l'esquerra (ex: `'0003'`).
    """
    with adr_lock(adr_dir):
        return _calculate_next_id_unlocked(adr_dir)


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
    """Escriu el fitxer ADR al directori corresponent prevenint Path Traversal i concurrència.

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

    with adr_lock(adr_dir):
        next_numeric = _calculate_next_id_unlocked(adr_dir)
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
