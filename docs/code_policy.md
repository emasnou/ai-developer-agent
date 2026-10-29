# 📜 Política de Codi, Documentació, Arquitectura i Seguretat

Aquest document constitueix la normativa tècnica innegociable del projecte **AI Developer Agent** i dels repositoris gestionats pels seus agents. Integra les directrius d'enginyeria de programari i **Docs-as-Code** definides a [`docs/Politica_Documentacio.md`](Politica_Documentacio.md) i és d'aplicació obligatòria tant per a desenvolupadors humans com per als agents autònoms ([`AnalystAgent`](../src/agents/analyst_agent.py), [`DeveloperAgent`](../src/agents/developer_agent.py) i [`CodeReviewAgent`](../src/agents/code_review_agent.py)).

---

## 1. Filosofia Docs-as-Code i Marc Diátaxis

1. **La documentació viu amb el codi**: Qualsevol canvi funcional, arquitectònic o de configuració ha d'anar acompanyat de l'actualització de la seva documentació a la mateixa Pull Request.
2. **Estructura documental basada en [Diátaxis](https://diataxis.fr/)**:
   - **Onboarding i Quickstart (`README.md`)**: Propòsit en 1 paràgraf, diagrama Mermaid d'alt nivell i guia d'execució reproduïble en menys de 5 minuts.
   - **Guies Operatives i Governança (`CONTRIBUTING.md`, `.env.example`, `CHANGELOG.md`)**: Flux de branques, *Conventional Commits*, contracte de variables d'entorn amb valors ficticis segurs i historial SemVer automatitzat (`Added`, `Changed`, `Fixed`, `Security`).
   - **Explicació d'Arquitectura (`docs/adr/`)**: Registre de les decisions arquitectòniques mitjançant *Architecture Decision Records* (ADR) seguint la plantilla oficial [`docs/adr/0000-template-adr-agent-ia.md`](adr/0000-template-adr-agent-ia.md).
   - **Referència Tècnica (`src/schemas/`, Docstrings i Type Hints)**: Especificació viva dels contractes de dades i funcions directament al codi font.

---

## 2. Nomenclatura, Estil i Disseny Modular (PEP 8 & Clean Code)

- **Variables, funcions i mètodes**: `snake_case` (ex: `generate_reset_token`, `set_active_repository`).
- **Classes i Models Pydantic**: `PascalCase` (ex: `PasswordResetTokenManager`, `DeveloperPlan`).
- **Constants de mòdul**: `UPPER_SNAKE_CASE` (ex: `TOKEN_EXPIRATION_MINUTES: int = 15`).
- **Atributs i mètodes interns/privats**: Prefixats amb un guió baix `_snake_case` (ex: `_build_workspace_env`).
- **Noms descriptius i semàntics**: Prohibides les abreviatures ambigües o d'una sola lletra fora d'iteradors curts (utilitzar `user_email` en lloc de `u_e`).
- **Mida de funcions i Principi de Responsabilitat Única (SRP)**:
  - Cap funció o mètode no ha de superar les **30-40 línies de codi efectiu**.
  - Cada funció ha de fer una única tasca i fer-la bé, delegant subtasques complexes en funcions auxiliars ben anomenades.
- **Injecció de dependències (DI)**:
  - Tots els agents i serveis han de permetre la injecció opcional de dependències (`llm_service`, `github_service`, `repo_name`, `client`) al constructor `__init__` per garantir l'aïllament en tests unitaris sense dependre de xarxa ni d'efectes secundaris en temps d'importació.
- **Formatat i Linting**: El codi ha de superar `ruff check src/ tests/` sense errors (límit de 100 caràcters per línia, importacions canòniques `from src...` ordenades segons `isort`).

---

## 3. Documentació Dins del Codi (*In-Code Documentation*)

### 3.1. Type Hints com a Documentació Viva (PEP 484)
- **Obligatorietat**: Totes les signatures de funcions, mètodes (inclosos constructors `__init__ -> None` i tests unitaris `test_* -> None`), fixtures de `pytest` i constants de mòdul han d'incloure anotacions de tipus explícites d'entrada i de retorn.
- **Verificació i Estàndard**: Els tipus actuen com a documentació viva verificada per l'IDE i l'analitzador estàtic `mypy src/` al pipeline de CI/CD. Preferir tipus natius moderns (`list[str]`, `dict[str, Any]`, `tuple[bool, str]`, `Optional[str]`).
  - Exemple: `def set_active_repository(self, repo_name: str) -> str:`

### 3.2. Docstrings Estructurats (Google Style — PEP 257)
- Tot mòdul, classe i funció o mètode públic ha d'incloure un docstring concís en **català** seguint l'estàndard **Google Style** (o NumPy/Sphinx de forma uniforme, sent **Google Style** l'estàndard canònic del projecte) amb les seccions `Args:`, `Returns:` i `Raises:` (quan la funció pugui llançar excepcions explícites).
- **Exemple canònic obligatori**:
  ```python
  def set_active_repository(self, repo_name: str) -> str:
      """Canvia el repositori actiu sobre el qual operen els mètodes del servei.

      Args:
          repo_name: Nom complet del repositori en format `propietari/repositori`.

      Returns:
          str: Nom validat del repositori que ha quedat actiu.

      Raises:
          ValueError: Si el format del nom del repositori no és vàlid o és insegur.
      """
  ```

### 3.3. Comentaris de Línia: El "Perquè" (*Why*), mai el "Què" (*What*)
- El codi ha de ser autoexplicatiu pel que fa a *què* fa; els comentaris de línia es reserven exclusivament per explicar el **perquè** d'una decisió no òbvia, una restricció de negoci, un *workaround* per un bug d'una API externa o una mitigació de seguretat.
- ❌ **Incorrecte (repeteix el codi — explica el "Què")**:
  ```python
  # Incrementa el comptador d'intents en 1
  attempt += 1
  ```
- ✅ **Correcte (explica el motiu tècnic, *workaround* o mitigació de seguretat — explica el "Perquè")**:
  ```python
  # Usem compare_digest en temps constant per mitigar atacs de canal lateral (OWASP A07)
  if not hmac.compare_digest(expected_signature, provided_signature):
      raise InvalidTokenError("Signatura invàlida.")
  ```

---

## 4. Contractes de Dades, Esquemes i Rendiment

- **Contractes de Dades Tipats (`src/schemas/`)**: Tota comunicació estructurada amb models LLM o APIs externes s'ha de definir mitjançant models **Pydantic** (`BaseModel` amb descripcions explícites a `Field(...)`), actuant com a font única de veritat tant per a la validació en temps d'execució com per a la documentació tècnica.
- **Complexitat Algorísmica**: Evitar bucles imbricats innecessaris ($O(n^2)$) sobre col·leccions; utilitzar estructures d'accés $O(1)$ (`set`, `dict`) per a cerques repetides.
- **Gestió de Memòria i Recursos**: Utilitzar generadors (`yield`) per a grans volums de dades i aplicar mecanismes de purga amortitzada en estructures en memòria amb creixement temporal (ex: tokens revocats o finestres de *rate limiting*) per prevenir denegació de servei per exhauriment de memòria (DoS/OOM).
- **Eficiència d'I/O**: Minimitzar crides repetides a APIs externes o disc dins de bucles i definir sempre `timeout` explícits en operacions de xarxa o subprocessos.

---

## 5. Seguretat per Disseny (OWASP Top 10)

1. **A01 — Broken Access Control & Path Traversal**:
   - Validar sempre qualsevol ruta de fitxer o nom de repositori extern (`validate_repo_name`).
   - Verificar amb `Path.resolve().is_relative_to(workspace_dir.resolve())` que cap operació d'escriptura no pugui sortir del directori permès.
2. **A02 — Cryptographic Failures**:
   - Utilitzar exclusivament primitius criptogràfics forts de la llibreria estàndard (`hashlib.scrypt`, `hmac` amb `SHA-256`, `secrets`). Prohibits `md5`, `sha1` sense sal o `random` per a tokens o contrasenyes.
   - Exigir claus secretes amb una entropia mínima de 32 bytes (256 bits).
3. **A03 — Injection (Command / SQL / Prompt)**:
   - Executar sempre subprocessos amb llistes d'arguments (`subprocess.run(["pytest", ...], shell=False, timeout=35)`). Prohibit l'ús de `shell=True`, `eval()` o `exec()`.
4. **A04 — Insecure Design**:
   - Validar rigorosament totes les entrades amb esquemes Pydantic o expressions regulars acotades (prevenint *ReDoS* i injecció de capçaleres CRLF).
5. **A05 — Security Misconfiguration & Secret Isolation**:
   - Mai incloure credencials hardcoded al codi font ni exposar traces internes o *stack traces* a l'usuari final.
   - Filtrar variables sensibles (`GITHUB_TOKEN`, `GEMINI_API_KEY`, `OPENAI_API_KEY`) abans d'executar subprocessos de test dins de `.workspace/` i excloure `.env` de qualsevol còpia o arbre Git.
6. **A07 — Identification & Authentication Failures**:
   - Retornar respostes genèriques idèntiques per evitar l'enumeració d'usuaris.
   - Validar signatures amb `hmac.compare_digest` (temps constant), aplicar consum atòmic protegit amb `threading.Lock` contra condicions de carrera (*TOCTOU*), tokens d'un sol ús amb expiració breu i *rate limiting* per IP i compte.

---

## 6. Documentació del Cicle de Desenvolupament i Disseny de Proves (PyTest & GitHub Templates)

- **Plantilles Estandarditzades de GitHub (`.github/`)**:
  - Totes les Issues funcionals han de seguir la plantilla [`.github/ISSUE_TEMPLATE/feature_request.md`](../.github/ISSUE_TEMPLATE/feature_request.md) amb **Història d'Usuari**, **Criteris d'Acceptació BDD (*Given-When-Then*)** i **Matriu de Proves (QA)**, gestionada per [`AnalystAgent`](../src/agents/analyst_agent.py) i [`src/utils/github_templates.py`](../src/utils/github_templates.py).
  - Les recomanacions de millora contínua post-auditoria han de seguir [`.github/ISSUE_TEMPLATE/improvement_recommendation.md`](../.github/ISSUE_TEMPLATE/improvement_recommendation.md) (renderitzada per [`CodeReviewAgent`](../src/agents/code_review_agent.py)), i els errors s'han de documentar amb [`.github/ISSUE_TEMPLATE/bug_report.md`](../.github/ISSUE_TEMPLATE/bug_report.md).
  - Totes les Pull Requests han d'utilitzar l'estructura de [`.github/pull_request_template.md`](../.github/pull_request_template.md) (renderitzada automàticament per [`DeveloperAgent`](../src/agents/developer_agent.py)), detallant el resum, l'Issue vinculada (`Closes #X`), els fitxers afectats, els intents de PyTest i la llista de verificació de seguretat OWASP Top 10.
- **Els tests documenten el comportament**: Els noms de les funcions de test (`test_<unitat>_<escenari>_<resultat_esperat>`) i el seu docstring han de descriure clarament el requisit funcional o de seguretat verificat (enfocament BDD *Given-When-Then*).
- **Aïllament absolut d'I/O (`tmp_path`)**: Els tests unitaris (`tests/unit/`) no han d'escriure mai a directoris reals del projecte (`logs/`, `.workspace/`, `CHANGELOG.md` arrel). S'ha d'utilitzar sempre la fixture `tmp_path` de `pytest`.
- **Execució 100% determinista i offline**: Els tests unitaris no han de dependre de connexió a Internet ni d'un fitxer `.env` local; totes les crides a GitHub o Gemini s'han de simular amb `unittest.mock.MagicMock` o `monkeypatch`.
- **Proves ràpides de límits i rotació**: Per validar rotació de fitxers o límits de mida, parametritzar llindars reduïts al test (ex: `max_bytes=200`) per executar-los en mil·lisegons sense bloquejos de disc.
- **Preservació quirúrgica de codi existent**: Quan es modifica un mòdul existent per afegir una funcionalitat, preservar totes les classes, signatures i comportaments previs que no siguin objecte directe del canvi.

---

## 7. Registre de Decisions d'Arquitectura (ADR) per a Humans i Agents d'IA

Quan un desenvolupador o un agent d'IA introdueixi un canvi estructural (nou patró d'arquitectura, nou servei d'integració, canvi en l'esquema de seguretat o d'aïllament de dades):
1. S'ha de documentar la decisió creant un fitxer numerat a [`docs/adr/`](adr/README.md) (ex: `docs/adr/0003-titol-decisio.md`) utilitzant la plantilla oficial [`docs/adr/0000-template-adr-agent-ia.md`](adr/0000-template-adr-agent-ia.md).
2. L'ADR ha de registrar explícitament el **Context**, els **Factors de Decisió**, la **Decisió Presa**, les **Alternatives Descartades**, les **Conseqüències (incloent impacte OWASP)** i l'**Evidència de Verificació amb PyTest**.

---

## 8. Automatització perquè la Documentació no Caduqui (Zero-Touch Docs-as-Code)

Per garantir que la documentació s'actualitzi de manera 100% automàtica i no depengui d'intervenció manual:
1. **Linter de Docstrings i Validació AST en CI/CD**:
   - Ruff aplica les regles `D` (`pydocstyle` convenció `google`) definides a [`pyproject.toml`](../pyproject.toml).
   - El motor [`src/utils/doc_updater.py`](../src/utils/doc_updater.py) (`python -m src.utils.doc_updater --validate-docstrings`) inspecciona l'arbre sintàctic (AST) de `src/` a [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) i [`.github/workflows/docs.yml`](../.github/workflows/docs.yml), bloquejant qualsevol PR amb mòduls, classes o funcions públiques sense docstring o sense anotació de tipus de retorn PEP 484.
2. **Sincronització Automàtica en Local (Temps de Commit i `DeveloperAgent`)**:
   - Els hooks locals de Git (`.git/hooks/pre-commit` i `.git/hooks/post-commit`) executen en local i en temps de commit `src.utils.doc_updater` i `src.utils.changelog_updater`, empaquetant qualsevol actualització de `CHANGELOG.md`, [`docs/reference/index.md`](reference/index.md) i [`docs/adr/README.md`](adr/README.md) dins del mateix commit local abans de fer `git push`.
   - Abans de publicar qualsevol branca o remediació, [`DeveloperAgent`](../src/agents/developer_agent.py) executa automàticament `_sync_workspace_changelog` ([`src/utils/changelog_updater.py`](../src/utils/changelog_updater.py)) i `_sync_workspace_documentation` ([`src/utils/doc_updater.py`](../src/utils/doc_updater.py)), actualitzant `CHANGELOG.md`, [`docs/reference/index.md`](reference/index.md) i la taula d'índex d'ADRs a [`docs/adr/README.md`](adr/README.md) dins del mateix commit.
3. **Portal Automàtic amb MkDocs Material i `mkdocstrings` (Sense mutació remota de `main`)**:
   - Configurat a [`mkdocs.yml`](../mkdocs.yml) i desplegat automàticament a GitHub Pages per [`.github/workflows/docs.yml`](../.github/workflows/docs.yml) a cada *push* a `main` en mode només lectura (`contents: read`), validant que la documentació ja arriba sincronitzada des de local i compilant el portal amb `mkdocs build --strict` sense crear commits remots a l'esquena del desenvolupador.
