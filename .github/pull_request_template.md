## 📋 Resum dels Canvis

{{SUMMARY}}

## 🔗 Issue Vinculada i Traçabilitat

- **Issue resolta:** Closes #{{ISSUE_NUMBER}} ({{ISSUE_TITLE}})
- **Branca origen:** `{{BRANCH_NAME}}`

## 📂 Fitxers Modificats / Creats

{{FILES_SUMMARY}}

## 🧪 Verificació i Tests Executats (PyTest)

- **Tests executats:** {{TESTS_STATUS}}
- **Intents d'auto-correcció al Workspace:** `{{ATTEMPTS}}`
- [x] Execució determinista i aïllada al `.workspace/` (ús de `tmp_path` i filtrat de secrets).
- [x] Validació sintàctica AST i compliment d'estàndards (`ruff` i `mypy`).

## 🛡️ Impacte de Seguretat (OWASP Top 10) i Governança (Docs-as-Code)

- [x] **OWASP Top 10:** Sense credencials hardcoded, validació d'entrades i prevenció de Path Traversal / Injecció.
- [x] **Documentació Dins del Codi:** Type Hints explícits (PEP 484), Docstrings Google Style (PEP 257) i comentaris centrats en el *Perquè*.
- [x] **Historial i Arquitectura:** `CHANGELOG.md` sincronitzat automàticament (i ADR a `docs/adr/` si s'introdueix un canvi arquitectònic).

