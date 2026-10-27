"""Plantilles de prompts de sistema per a l'Agent Analista (`AnalystAgent`)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.utils.github_templates import (
    FEATURE_ISSUE_TEMPLATE_REL_PATH,
    load_github_template,
)

_DEFAULT_FEATURE_TEMPLATE_BODY: str = """## 📝 Descripció i Història d'Usuari
**Com a** [Rol d'usuari]
**Vull** [Acció o funcionalitat]
**Per a** [Benefici o valor afegit]

## 🎯 Criteris d'Acceptació
- [ ] **Escenari 1:** [Títol de l'escenari]
  - **Given (Donat):** [Estat inicial]
  - **When (Quan):** [Acció de l'usuari]
  - **Then (Aleshores):** [Resultat esperat]

- [ ] **Escenari 2:** [Títol de l'escenari]
  - **Given (Donat):** [Estat inicial]
  - **When (Quan):** [Acció de l'usuari]
  - **Then (Aleshores):** [Resultat esperat]

## 🧪 Matriu de Proves de Qualitat (QA Requirements)
### Tests Unitaris
- [ ] Test 1: [Què s'ha de provar a nivell de funció/component]
- [ ] Test 2: [Cas límit o d'error]

### Tests d'Integració / E2E
- [ ] Test 1: [Flux complet d'usuari o integració de serveis]

## 🛡️ Requisits de Seguretat i Documentació (Docs-as-Code)
- [ ] Compliment d'estàndards OWASP Top 10 i validació d'entrades.
- [ ] Type Hints (PEP 484) i Docstrings Google Style (PEP 257) en català.

## 📌 Etiquetes Recomanades
`enhancement`, `agent-qa-ready`"""


def build_analyst_system_prompt(
    template_path: Optional[Path] = None,
    workspace_dir: Optional[Path] = None,
) -> str:
    """Construeix el prompt de sistema de l'AnalystAgent injectant la plantilla d'Issue de GitHub.

    Args:
        template_path: Ruta opcional a una plantilla d'Issue personalitzada.
        workspace_dir: Directori opcional del workspace actiu.

    Returns:
        str: Prompt de sistema complet amb l'estructura de `.github/ISSUE_TEMPLATE/feature_request.md`.
    """
    rel_path = (
        str(template_path) if template_path is not None else FEATURE_ISSUE_TEMPLATE_REL_PATH
    )
    issue_template = load_github_template(
        relative_path=rel_path,
        workspace_dir=workspace_dir,
        fallback=_DEFAULT_FEATURE_TEMPLATE_BODY,
        strip_frontmatter=True,
    )
    return (
        "Ets un Analista de Programari i Product Owner expert en metodologies àgils.\n"
        "La teva tasca és agafar una idea o requeriment d'una aplicació i generar una "
        "especificació detallada en format Markdown per a una Issue de GitHub seguint "
        "la plantilla oficial del repositori (`.github/ISSUE_TEMPLATE/feature_request.md`).\n\n"
        "La teva resposta ha de tenir EXACTAMENT aquesta estructura en Markdown:\n\n"
        f"{issue_template}\n"
    )


ANALYST_SYSTEM_PROMPT: str = build_analyst_system_prompt()
