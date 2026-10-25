"""Utilitats centralitzades per a l'extracció, reparació i normalització de respostes JSON/YAML del LLM.

Aquest mòdul unifica la lògica resilient de parseig utilitzada pels diferents agents,
eliminant la duplicació de codi (DRY) i garantint el compliment del principi de responsabilitat única (SRP).
"""

from __future__ import annotations

import json
import re
from typing import Any, Sequence

import yaml
from json_repair import repair_json

_FENCE_START_RE = re.compile(r"```(?:json|yaml)?\s*", flags=re.MULTILINE)
_FENCE_END_RE = re.compile(r"```\s*$", flags=re.MULTILINE)
_TRIPLE_QUOTES_RE = re.compile(r'("(?:content|code)"\s*:\s*)(\'\'\'|""")([\s\S]*?)(\2)')
_INVALID_ESCAPE_RE = re.compile(r'\\(?![\\"/bfnrtu]|u[0-9a-fA-F]{4})')


def clean_markdown_fences(text: str) -> str:
    """Elimina els blocs de codi Markdown (```json o ```yaml) d'una cadena de text.

    Args:
        text: Cadena de text original retornada pel LLM.

    Returns:
        str: Text netejat sense delimitadors de bloc Markdown.
    """
    cleaned = _FENCE_START_RE.sub("", text.strip())
    return _FENCE_END_RE.sub("", cleaned).strip()


def replace_triple_quoted_strings(text: str) -> str:
    """Converteix valors delimitats per triples cometes Python en cadenes JSON vàlides.

    Args:
        text: Text JSON/pseudo-JSON que pot contenir '''...''' o \"\"\"...\"\"\".

    Returns:
        str: Text amb els blocs de triples cometes serialitzats amb json.dumps.
    """
    def _replacer(match: re.Match[str]) -> str:
        prefix = match.group(1)
        code = match.group(3)
        return f"{prefix}{json.dumps(code)}"

    return _TRIPLE_QUOTES_RE.sub(_replacer, text)


def extract_json_object_bounds(text: str) -> str:
    """Extreu la subcadena compresa entre la primera clau '{' i l'última '}'.

    Args:
        text: Text del qual es vol aïllar l'objecte JSON principal.

    Returns:
        str: Subcadena amb l'objecte candidat o el text original si no hi ha claus.
    """
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1]
    return text.strip()


def sanitize_invalid_escapes(text: str) -> str:
    """Escapa barres invertides solitàries que no formen seqüències d'escapament JSON vàlides.

    Args:
        text: Cadena JSON amb possibles expressions regulars o barres sense escapar.

    Returns:
        str: Cadena amb les barres invertides sanititzades.
    """
    return _INVALID_ESCAPE_RE.sub(r"\\\\", text)


def normalize_developer_files(data: dict[str, Any]) -> dict[str, Any]:
    """Normalitza el diccionari de sortida del DeveloperAgent assegurant l'estructura de 'files'.

    Args:
        data: Diccionari cru extret de la resposta del LLM.

    Returns:
        dict[str, Any]: Diccionari amb la llista 'files' validada i normalitzada.
    """
    if not isinstance(data, dict):
        return data

    files = data.get("files", [])
    normalized_files: list[dict[str, str]] = []
    for item in files:
        if isinstance(item, dict) and "path" in item and "content" in item:
            normalized_files.append({
                "path": str(item["path"]).strip(),
                "action": str(item.get("action", "create_or_modify")),
                "content": str(item["content"]),
            })
    data["files"] = normalized_files
    return data


def _extract_files_from_repaired(repaired: Any) -> dict[str, Any] | None:
    """Extreu un diccionari amb clau 'files' a partir del resultat de repair_json o YAML.

    Args:
        repaired: Estructura retornada per repair_json o yaml.safe_load.

    Returns:
        dict[str, Any] | None: Diccionari normalitzat si conté fitxers vàlids, o None.
    """
    if isinstance(repaired, dict):
        if "files" in repaired:
            return normalize_developer_files(repaired)
        for alt_key in ("file", "files_to_modify", "changes"):
            if alt_key in repaired:
                val = repaired[alt_key]
                repaired["files"] = val if isinstance(val, list) else [val]
                return normalize_developer_files(repaired)
    elif isinstance(repaired, list):
        for elem in repaired:
            if isinstance(elem, dict) and "files" in elem:
                return normalize_developer_files(elem)
        if repaired and all(isinstance(item, dict) and "path" in item for item in repaired):
            return normalize_developer_files({"summary": "Canvis generats", "files": repaired})
    return None


def parse_developer_json_response(text: str) -> dict[str, Any]:
    """Extreu i repara l'objecte JSON/YAML de pla de desenvolupament d'una resposta del LLM.

    Args:
        text: Resposta en text cru retornada pel model LLM.

    Returns:
        dict[str, Any]: Diccionari normalitzat amb les claus 'summary' i 'files'.

    Raises:
        ValueError: Si la resposta és buida.
        json.JSONDecodeError: Si cap estratègia de recuperació pot extreure un JSON vàlid.
    """
    if not text or not text.strip():
        raise ValueError("Resposta buida del model LLM.")

    # 1. Càrrega directa nativa (habitual amb Structured Outputs)
    try:
        parsed = json.loads(text.strip(), strict=False)
        if isinstance(parsed, dict) and "files" in parsed:
            return normalize_developer_files(parsed)
    except Exception:
        pass

    # 2. Neteja de blocs Markdown i triples cometes
    cleaned = clean_markdown_fences(text)
    preprocessed = replace_triple_quoted_strings(cleaned)
    json_candidate = extract_json_object_bounds(preprocessed)

    # 3. Intent natiu i amb barres sanititzades sobre el candidat
    for candidate in (json_candidate, sanitize_invalid_escapes(json_candidate)):
        try:
            parsed = json.loads(candidate, strict=False)
            if isinstance(parsed, dict) and "files" in parsed:
                return normalize_developer_files(parsed)
        except Exception:
            pass

    # 4. Intent amb json_repair sobre el candidat i sobre el text netejat complet
    for source in (json_candidate, cleaned):
        try:
            extracted = _extract_files_from_repaired(repair_json(source, return_objects=True))
            if extracted is not None:
                return extracted
        except Exception:
            pass

    # 5. Fallback amb PyYAML
    try:
        extracted_yaml = _extract_files_from_repaired(yaml.safe_load(json_candidate))
        if extracted_yaml is not None:
            return extracted_yaml
    except Exception:
        pass

    return normalize_developer_files(json.loads(json_candidate, strict=False))


def parse_generic_json_response(
    text: str,
    expected_keys: Sequence[str] = ("approved", "report", "improvements"),
) -> dict[str, Any]:
    """Extreu i parseja un objecte JSON genèric (com informes de Code Review) de manera resilient.

    Args:
        text: Resposta crua del model LLM.
        expected_keys: Claus esperades quan cal desambiguar llistes retornades per repair_json.

    Returns:
        dict[str, Any]: Diccionari extret o diccionari buit `{}` si no és possible parsejar-lo.
    """
    if not text or not text.strip():
        return {}

    cleaned = clean_markdown_fences(text)
    for candidate in (text.strip(), cleaned):
        try:
            parsed = json.loads(candidate, strict=False)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    try:
        repaired = repair_json(cleaned, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
        if isinstance(repaired, list):
            for elem in repaired:
                if isinstance(elem, dict) and any(k in elem for k in expected_keys):
                    return elem
    except Exception:
        pass

    json_str = extract_json_object_bounds(cleaned)
    for candidate in (json_str, sanitize_invalid_escapes(json_str)):
        try:
            parsed = json.loads(candidate, strict=False)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}

