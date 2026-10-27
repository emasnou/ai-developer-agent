# 🤝 Guia de Contribució (CONTRIBUTING)

Gràcies pel teu interès a contribuir a **AI Developer Agent**! Aquest document estableix el flux de branques, les convencions de commits, els estàndards d'arquitectura i els requisits per obrir una Pull Request tant per a desenvolupadors humans com per als agents autònoms del projecte, seguint el marc **Docs-as-Code** definit a [`docs/Politica_Documentacio.md`](docs/Politica_Documentacio.md).

---

## 1. Configuració de l'Entorn de Desenvolupament

1. Clona el repositori i crea un entorn virtual amb Python `3.10` o superior:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Instal·la el projecte en mode editable juntament amb les dependències de desenvolupament i qualitat:
   ```bash
   pip install -e ".[dev]"
   ```
3. Copia la plantilla [`.env.example`](.env.example) a `.env` si necessites executar proves d'integració contra GitHub o Google Gemini:
   ```bash
   cp .env.example .env
   ```
   > **Nota:** Tota la bateria de tests unitaris (`tests/unit/`) està dissenyada per executar-se 100% *offline* sense necessitat de credencials reals.

---

## 2. Flux de Branques Git i Format de Commits

### 2.1 Política de Branques
* **Branca principal (`main`)**: Conté sempre codi estable que ha superat el pipeline de CI/CD i les auditories de qualitat i seguretat. No es permeten *commits* directes sense validació.
* **Branques de desenvolupament**:
  * **Noves funcionalitats vinculades a una Issue**: `feature/issue-<numero>` (ex: `feature/issue-12`). Aquest és el format estàndard generat també pel [`DeveloperAgent`](src/agents/developer_agent.py).
  * **Correccions d'errors**: `fix/<descripcio-breu>` (ex: `fix/json-escape-parser`).
  * **Pegats de seguretat**: `security/<descripcio-breu>` (ex: `security/path-traversal-guard`).
  * **Documentació o manteniment**: `docs/<descripcio>` o `chore/<descripcio>`.

### 2.2 Format dels Commits (*Conventional Commits*)
Tots els missatges de commit han de seguir l'especificació **[Conventional Commits](https://www.conventionalcommits.org/)**:

```text
<tipus>(<abast opcional>): <descripció breu en minúscules i imperatiu/participi>
```

Aquest format permet que l'eina [`src/utils/changelog_updater.py`](src/utils/changelog_updater.py) i el workflow [`.github/workflows/changelog.yml`](.github/workflows/changelog.yml) classifiquin automàticament els canvis a [`CHANGELOG.md`](CHANGELOG.md) segons les categories de *Keep a Changelog*:

| Prefix de Commit | Categoria a `CHANGELOG.md` | Ús i Exemple |
| :--- | :--- | :--- |
| `feat:` | `Added` | Nova funcionalitat o capacitat (ex: `feat(multi-repo): selecció de repositori al menú CLI`). |
| `fix:` | `Fixed` | Correcció d'un error o bug (ex: `fix(developer): descàrrega de la branca de la PR en remediació`). |
| `security:` / `sec:` | `Security` | Mitigació de vulnerabilitats OWASP (ex: `security(github): validació contra Path Traversal`). |
| `refactor:` | `Changed` | Canvi intern d'arquitectura sense alterar el comportament extern. |
| `perf:` | `Changed` | Millora de rendiment o optimització algorísmica. |
| `docs:` | `Changed` | Creació o actualització de documentació i docstrings. |
| `test:` / `ci:` / `chore:` | *(Manteniment intern)* | Addició de tests, canvis a GitHub Actions o actualització de dependències. |

---

## 3. Estàndards de Codi i Arquitectura

Qualsevol contribució ha de complir estrictament la política definida a [`docs/code_policy.md`](docs/code_policy.md):

1. **Docstrings en format Google Style (PEP 257)**:
   Tots els mòduls, classes, mètodes i funcions públiques han d'incloure docstrings en català amb les seccions `Args:`, `Returns:` i `Raises:`.
2. **Tipat Estàtic (PEP 484)**:
   Totes les signatures de funcions i mètodes han d'incloure anotacions de tipus explícites verificables amb `mypy`.
3. **Principi de Responsabilitat Única (SRP)**:
   Mantenir les funcions curtes ($\le$ 35 línies de codi efectiu), delegant subtasques en mètodes auxiliars ben anomenats.
4. **Creació o Extensió d'Agents (`BaseAgent`)**:
   * Qualsevol agent dins de `src/agents/` ha d'heretar de [`BaseAgent`](src/agents/base_agent.py).
   * Permetre la injecció opcional de `llm_service`, `github_service` i `repo_name` al constructor `__init__` per garantir el suport multi-repositori i els tests unitaris amb *mocks*.
   * Utilitzar `self.logger` per al registre estructurat en JSON (`logs/agents.log`).
   * Definir els esquemes de sortida estructurada amb Pydantic a [`src/schemas/agent_schemas.py`](src/schemas/agent_schemas.py) i els prompts a `src/prompts/`.

---

## 4. Disseny de Proves (PyTest)

* **Aïllament total d'I/O (`tmp_path`)**: Cap test unitari no ha d'escriure mai a `logs/`, `.workspace/` ni a cap directori de producció. Utilitza sempre la fixture `tmp_path` de `pytest`.
* **Injecció de Mocks**: En provar agents o serveis, injecta instàncies simulades (`unittest.mock.MagicMock` o `pytest-mock`) per evitar qualsevol crida de xarxa.
* **Seguretat (OWASP Top 10)**: Si s'afegeixen funcionalitats que manipulen credencials, rutes de fitxers, tokens o subprocessos, cal incloure tests específics de seguretat (comparació en temps constant, prevenció de *Path Traversal*, *TOCTOU* i sanejament d'entorn).

---

## 5. Plantilles de GitHub i Requisits per Obrir Issues i Pull Requests

Tant els desenvolupadors humans (via la interfície web de GitHub) com els agents autònoms (via [`src/utils/github_templates.py`](src/utils/github_templates.py)) utilitzen les plantilles oficials del directori `.github/`:

* **Plantilles d'Issues (`.github/ISSUE_TEMPLATE/`)**:
  * [`.github/ISSUE_TEMPLATE/feature_request.md`](.github/ISSUE_TEMPLATE/feature_request.md): Especificació funcional amb Història d'Usuari, Criteris d'Acceptació BDD (*Given-When-Then*) i Matriu de Proves de Qualitat (usada automàticament per [`AnalystAgent`](src/agents/analyst_agent.py)).
  * [`.github/ISSUE_TEMPLATE/improvement_recommendation.md`](.github/ISSUE_TEMPLATE/improvement_recommendation.md): Millores contínues d'arquitectura, rendiment o seguretat extretes durant l'auditoria de PRs (usada automàticament per [`CodeReviewAgent`](src/agents/code_review_agent.py)).
  * [`.github/ISSUE_TEMPLATE/bug_report.md`](.github/ISSUE_TEMPLATE/bug_report.md): Informe d'errors o incidències de seguretat OWASP amb passos de reproducció BDD i requisit de test de regressió.
* **Plantilla de Pull Request ([`.github/pull_request_template.md`](.github/pull_request_template.md))**:
  * Renderitzada automàticament per [`DeveloperAgent`](src/agents/developer_agent.py) en publicar una solució validada amb PyTest.

Abans d'obrir una Pull Request cap a `main`, assegura't de complir tots els requisits següents:

1. **Vinculació amb Issue i Plantilla**: La PR ha de seguir l'estructura de [`.github/pull_request_template.md`](.github/pull_request_template.md), referenciar la Issue que resol (ex: `Closes #15`) i provenir d'una branca amb nomenclatura vàlida (`feature/issue-15`).
2. **Documentació sincronitzada (*Docs-as-Code*)**:
   * Si s'afegeixen variables d'entorn, han d'estar documentades a [`.env.example`](.env.example).
   * Totes les funcions noves o modificades tenen el seu docstring Google Style i tipat PEP 484.
   * S'ha actualitzat [`CHANGELOG.md`](CHANGELOG.md) (automàticament via `python3 -m src.utils.changelog_updater` o al workflow de CI).
3. **Verificació de Qualitat i Tests en Local**:
   Executa les comandes següents i verifica que finalitzen sense errors:

```bash
# 1. Comprovació d'estil, imports i seguretat amb Ruff
ruff check src/ tests/

# 2. Verificació estricta de tipat estàtic amb Mypy
mypy src/

# 3. Execució de la bateria de tests unitaris amb cobertura
pytest -v tests/unit/ --cov=src --cov-report=term-missing

# 4. Validació de docstrings, tipus i sincronització automàtica de docs i CHANGELOG.md
python3 -m src.utils.doc_updater --validate-docstrings
python3 -m src.utils.doc_updater
python3 -m src.utils.changelog_updater
```
