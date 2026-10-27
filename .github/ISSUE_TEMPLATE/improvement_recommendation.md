---
name: "💡 Millora Recomanada (Code Review / Deute Tècnic)"
about: "Recomanació d'arquitectura, rendiment o seguretat identificada durant el Code Review"
title: "enhancement: "
labels: ["enhancement", "agent-review"]
assignees: []
---

## 💡 Millora Recomanada

- **Pull Request d'origen:** {{PR_REFERENCE}}
- **Fitxer de codi afectat:** `{{CODE_FILENAME}}`
- **Fitxer de tests associat:** `{{TEST_FILENAME}}`

### 🔍 Context i Motivació
{{CONTEXT}}

### 🛠️ Proposta d'Implementació
{{PROPOSAL}}

### 🧪 Criteris de Verificació (PyTest)
- [ ] Afegir o actualitzar tests unitaris a `{{TEST_FILENAME}}` utilitzant `tmp_path` i mocks deterministes.
- [ ] Verificar el compliment de `ruff check src/ tests/` i `mypy src/`.

