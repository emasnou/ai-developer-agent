# 🤝 Guia de Contribució (CONTRIBUTING)

Gràcies pel teu interès a contribuir a **AI Developer Agent**! Aquest document estableix els estàndards de desenvolupament, arquitectura i control de qualitat que segueix tant l'equip humà com els mateixos agents autònoms del projecte.

---

## 1. Configuració de l'Entorn de Desenvolupament

1. Clona el repositori i crea un entorn virtual amb Python 3.10 o superior:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Instal·la el projecte en mode editable juntament amb les dependències de desenvolupament i qualitat:
   ```bash
   pip install -e ".[dev]"
   ```
3. Copia la plantilla `.env.example` a `.env` si necessites executar proves d'integració contra GitHub o Google Gemini:
   ```bash
   cp .env.example .env
   ```
   > **Nota:** Tota la bateria de tests unitaris (`tests/unit/`) està dissenyada per executar-se 100% *offline* sense necessitat de credencials reals.

---

## 2. Flux de Treball Git i Nomenclatura de Branques

* **Branca principal**: `main` conté sempre codi estable que ha superat el pipeline de CI/CD.
* **Nomenclatura de branques**:
  * Noves funcionalitats vinculades a una Issue: `feature/issue-<numero>` (ex: `feature/issue-12`)
  * Correccions d'errors: `fix/<descripcio-breu>` (ex: `fix/json-escape-parser`)
  * Millores de documentació o configuració: `docs/<descripcio>` o `chore/<descripcio>`

### Conventional Commits
Els missatges de commit han de seguir l'especificació **Conventional Commits**:
* `feat:` Nova funcionalitat o capacitat d'agent (ex: `feat: implementat AnalystAgent amb plantilla BDD`).
* `fix:` Correcció d'un error (ex: `fix: descàrrega de la branca de la PR en mode remediació`).
* `refactor:` Canvi intern d'arquitectura sense alterar el comportament extern (ex: `refactor: extret BaseAgent i parser JSON centralitzat`).
* `docs:` Canvis exclusius en documentació o docstrings.
* `test:` Addició o millora de proves unitàries o d'integració.
* `ci:` Modificacions als workflows de GitHub Actions o eines de qualitat.

---

## 3. Estàndards de Codi i Arquitectura

Qualsevol contribució ha de complir estrictament la política definida a [`docs/code_policy.md`](docs/code_policy.md):

1. **Docstrings en format Google Style (PEP 257)**:
   Tots els mòduls, classes, mètodes i funcions han d'incloure docstrings en català amb les seccions `Args:`, `Returns:` i `Raises:`.
2. **Tipat Estàtic (PEP 484)**:
   Totes les signatures de funcions i mètodes han d'incloure anotacions de tipus explícites.
3. **Principi de Responsabilitat Única (SRP)**:
   Mantenir les funcions curtes (idealment $\le$ 35 línies), delegant subtasques en mètodes auxiliars ben anomenats.
4. **Creació o Extensió d'Agents (`BaseAgent`)**:
   * Qualsevol nou agent dins de `src/agents/` ha d'heretar de `BaseAgent` (`src/agents/base_agent.py`).
   * Utilitzar `self.logger` per al registre estructurat en JSON (`logs/agents.log`).
   * Permetre sempre la injecció opcional de `llm_service` i `github_service` al constructor `__init__` per facilitar els tests unitaris amb *mocks*.
   * Definir els esquemes de sortida estructurada amb Pydantic a `src/schemas/agent_schemas.py` i els prompts a `src/prompts/`.

---

## 4. Disseny de Proves (PyTest)

* **Aïllament d'I/O (`tmp_path`)**: Cap test unitari no ha d'escriure mai a `logs/`, `.workspace/` ni a cap directori de producció. Utilitza sempre la fixture `tmp_path` de `pytest`.
* **Injecció de Mocks**: En provar agents o serveis, injecta instàncies simulades (`unittest.mock.MagicMock` o `pytest-mock`) per evitar crides de xarxa.
* **Seguretat (OWASP Top 10)**: Si s'afegeixen funcionalitats que manipulen credencials, tokens o subprocessos, cal incloure tests específics de seguretat (temps constant, prevenció de TOCTOU, sanejament d'entorn).

---

## 5. Llista de Comprovació abans d'obrir una Pull Request

Abans d'enviar una Pull Request, executa localment les verificacions del pipeline de CI:

```bash
# 1. Comprovació d'estil i importacions amb Ruff
ruff check src/ tests/

# 2. Verificació de tipat estàtic amb Mypy
mypy src/

# 3. Execució de la bateria de tests unitaris amb cobertura
pytest -v tests/unit/ --cov=src --cov-report=term-missing
```

