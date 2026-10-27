# 🖥️ Scripts Operatius en Bash (`bin/`)

Aquest directori centralitza els scripts en Bash amb paràmetres d'entrada per executar totes les funcionalitats d'automatització, desenvolupament, qualitat i documentació (*Docs-as-Code*) definides al projecte.

Tots els scripts comparteixen la biblioteca comuna [`bin/_common.sh`](_common.sh), que detecta automàticament l'arrel del projecte i l'entorn virtual Python (`.venv/` o `venv/`) independentment del directori des d'on s'executin.

> **Nota de permisos:** Si és el primer cop que clones el repositori, assegura permisos d'execució amb:
> ```bash
> chmod +x bin/ai-*
> ```

---

## 📋 Catàleg de Scripts Disponibles

| Script | Funcionalitat Principal | Mòdul Subjacent |
| :--- | :--- | :--- |
| **[`bin/ai-agent`](ai-agent)** | Executa l'agent multi-repositori (menú interactiu o accions directes per paràmetre: Analista, Desenvolupador, Code Reviewer, Remediació). | [`src/main.py`](../src/main.py) i `src/agents/*` |
| **[`bin/ai-docs`](ai-docs)** | Sincronitza automàticament `docs/reference/index.md` i `docs/adr/README.md`, valida docstrings/tipus per AST i compila o serveix **MkDocs Material**. | [`src/utils/doc_updater.py`](../src/utils/doc_updater.py) i [`mkdocs.yml`](../mkdocs.yml) |
| **[`bin/ai-changelog`](ai-changelog)** | Actualitza automàticament `CHANGELOG.md` des de Git (*Conventional Commits*), afegeix entrades i publica versions SemVer (`MAJOR.MINOR.PATCH`). | [`src/utils/changelog_updater.py`](../src/utils/changelog_updater.py) |
| **[`bin/ai-quality`](ai-quality)** | Executa la suite de qualitat, seguretat OWASP (`ruff` + `bandit`), tipat estàtic (`mypy`), docstrings AST i tests unitaris (`pytest` + cobertura). | `.github/workflows/ci.yml` |
| **[`bin/ai-adr`](ai-adr)** | Llista, crea nous *Architecture Decision Records* numerats seqüencialment (`docs/adr/NNNN-*.md`) i sincronitza l'índex `docs/adr/README.md`. | [`docs/adr/0000-template-adr-agent-ia.md`](../docs/adr/0000-template-adr-agent-ia.md) |

---

## 🚀 Guia d'Ús i Paràmetres per Script

### 1. [`bin/ai-agent`](ai-agent) — Agent Autònom Multi-Repositori

```bash
# Obrir el menú interactiu principal
./bin/ai-agent

# Obrir el menú preseleccionant un repositori de GitHub concret
./bin/ai-agent --repo emasnou/ai-developer-agent

# Llistar tots els repositoris disponibles
./bin/ai-agent --list-repos

# Crear una nova Issue directament amb l'AnalystAgent (usa .github/ISSUE_TEMPLATE/feature_request.md)
./bin/ai-agent --repo emasnou/ai-developer-agent --action analyst \
  --title "Autenticació OAuth2" \
  --description "Implementar flux OAuth2 amb validació d'estat CSRF"

# Desenvolupar i validar amb PyTest una Issue concreta amb el DeveloperAgent
./bin/ai-agent --repo emasnou/ai-developer-agent --action develop --issue 12

# Auditar una Pull Request amb el CodeReviewAgent (PEP 8 + OWASP Top 10)
./bin/ai-agent --repo emasnou/ai-developer-agent --action review --pr 15

# Remediar automàticament una Pull Request segons el Code Review
./bin/ai-agent --repo emasnou/ai-developer-agent --action remediate --pr 15
```

---

### 2. [`bin/ai-docs`](ai-docs) — Motor Docs-as-Code i Portal MkDocs

```bash
# Sincronitzar automàticament docs/reference/index.md i l'índex d'ADRs (opció per defecte)
./bin/ai-docs

# Validar per AST que el 100% de mòduls, classes i funcions públiques de src/ tenen docstring i tipus
./bin/ai-docs --validate-docstrings

# Comprovar si la documentació està sincronitzada (sense modificar fitxers, útil per a CI)
./bin/ai-docs --check

# Executar validació AST + sincronització + compilació estricta de MkDocs Material
./bin/ai-docs --all

# Aixecar el servidor local de previsualització de MkDocs Material al port 8000
./bin/ai-docs --serve --port 8000
```

---

### 3. [`bin/ai-changelog`](ai-changelog) — Gestió Automàtica de `CHANGELOG.md`

```bash
# Sincronitzar [Unreleased] a partir dels commits recents de Git
./bin/ai-changelog

# Afegir una entrada explícita en format Conventional Commits
./bin/ai-changelog --add "feat(cli): afegir scripts operatius al directori bin/"

# Promocionar la secció [Unreleased] a una nova versió SemVer (ex: 0.4.0)
./bin/ai-changelog --release 0.4.0

# Mostrar per terminal el contingut actual de [Unreleased]
./bin/ai-changelog --show
```

---

### 4. [`bin/ai-quality`](ai-quality) — Suite de Qualitat, Seguretat i Tests

```bash
# Executar tota la suite completa (Ruff + Docstrings AST + Mypy + PyTest amb cobertura)
./bin/ai-quality

# Executar només el linter Ruff i la verificació de tipus Mypy
./bin/ai-quality --lint --types

# Aplicar correccions automàtiques amb Ruff i sincronitzar documentació
./bin/ai-quality --fix

# Executar només l'auditoria de seguretat SAST (OWASP Top 10 / Bandit)
./bin/ai-quality --security

# Executar tests unitaris filtrant per expressió (-k)
./bin/ai-quality --test --filter "test_doc_updater or test_github_templates"
```

---

### 5. [`bin/ai-adr`](ai-adr) — Gestió d'Architecture Decision Records

```bash
# Llistar tots els ADRs registrats a docs/adr/
./bin/ai-adr --list

# Crear un nou ADR numerat automàticament i sincronitzar docs/adr/README.md
./bin/ai-adr --new "Estratègia de Rate Limiting Distribuït" --status Proposat --issue "#21"

# Forçar la sincronització de la taula d'índex a docs/adr/README.md
./bin/ai-adr --sync
```

