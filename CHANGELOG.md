# 📦 Historial de Canvis (CHANGELOG)

Tots els canvis rellevants d'aquest projecte es documenten en aquest fitxer.
El format es basa en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) i el projecte segueix [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`), agrupant els canvis en `Added`, `Changed`, `Fixed` i `Security`.

> **Nota d'automatització:** Aquest fitxer s'actualitza automàticament a partir dels missatges *Conventional Commits* mitjançant [`src/utils/changelog_updater.py`](src/utils/changelog_updater.py) i el workflow de GitHub Actions [`.github/workflows/changelog.yml`](.github/workflows/changelog.yml).

## [Unreleased]

### Added
- **Motor d'Actualització Automàtica de Documentació (`src/utils/doc_updater.py`, `.github/workflows/docs.yml`)**: Eina CLI (`ai-docs`) que inspecciona l'arbre sintàctic (AST) de `src/`, valida el 100% de docstrings i anotacions de tipus de retorn PEP 484, regenera automàticament `docs/reference/index.md` i sincronitza la taula d'índex d'ADRs a `docs/adr/README.md`.
- **Portal de Documentació Automàtic amb MkDocs (`mkdocs.yml`, `docs/index.md`, `docs/reference/index.md`)**: Configuració de MkDocs Material amb `mkdocstrings` (estil Google) i desplegament continu a GitHub Pages des de `.github/workflows/docs.yml`.
- **Plantilles Oficials de GitHub i Motor de Renderització (`.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`, `src/utils/github_templates.py`)**: Plantilles estandarditzades per a Issues (`feature_request.md`, `improvement_recommendation.md`, `bug_report.md`) i Pull Requests integrades automàticament a `AnalystAgent`, `DeveloperAgent` i `CodeReviewAgent`.
- **Estructura d'Architecture Decision Records (`docs/adr/`, `src/schemas/agent_schemas.py`)**: Plantilla `0000-template-adr-agent-ia.md`, model Pydantic `ArchitectureDecisionRecord` i registres fundacionals `ADR-0001` i `ADR-0002`.
- Resolució Issue #9 (Implementació del mòdul centralitzat de registre i rotació de logs d'auditoria en format JSON per als agents, integrat amb AnalystAgent, DeveloperAgent i CodeReviewAgent, acompanyat de tests unitaris robustos basats en tmp_path i mides reduïdes.)
- **issue-19**: Resolució Issue #19 (Implementació de la generació, numeració seqüencial i materialització automàtica d'ADRs (Architecture Decision Records) pel DeveloperAgent.)
- **issue-29**: Resolució Issue #29 (Afegir exportació dels esquemes FinOps a src/schemas/__init__.py i implementar la suite completa de tests de validació de restriccions no negatives (ge=0) a TokenUsage i mètriques FinOps.)
- **issue-23**: Resolució Issue #23 (Implementació del servei MetricsTracker per al seguiment de sessions, mesura de latències amb context managers, ràtios d'eficiència (TPS) i exportació d'informes FinOps.)
- **issue-7**: Resolució Issue #7 (Integració de logs estructurats i monitoratge de seguretat a src/password_reset.py per a SIEM i detecció d'intrusions)
- **issue-21**: Resolució Issue #21 (Implementació de protecció contra concurrència atòmica (inter-procés i multi-fil) i ordenació estrictament numèrica a get_next_adr_id i materialize_adr_file.)
- **issue-42**: Resolució Issue #42 (Afegir límit de mida màxima (max_payload_size) a validate_request i a l'AnalyticsAgent per protecció contra atacs DoS/OOM)
- **issue-31**: Resolució Issue #31 (Parametrització dels tests de validació per a camps numèrics negatius a TokenUsage mitjançant pytest.mark.parametrize.)
- **issue-33**: Resolució Issue #33 (Implementació d'un límit configurable de registres històrics amb buffer circular (collections.deque) i purga periòdica a MetricsTracker per garantir un consum constant de memòria (OWASP A04 - DoS/OOM).)
- **issue-35**: Resolució Issue #35 (Implementat el sanejament d'entrades per prevenir Log Injection (CWE-117) al registre d'auditoria de restabliment de contrasenyes.)
- **issue-46**: Resolució Issue #46 (Encapsulació del payload serialitzat a AnalyticsQuery mitjançant PrivateAttr per garantir concurrència thread-safe a AnalyticsAgent)
- **issue-50**: Resolució Issue #50 (Configuració de DEFAULT_MAX_RECORDS_LIMIT com a valor per defecte a MetricsTracker.__init__ per prevenir riscos de memòria no acotada (OWASP A04))

### Changed
- **Sincronització Documental Autònoma al `DeveloperAgent` (`src/agents/developer_agent.py`)**: Integració de `_sync_workspace_documentation` per actualitzar `docs/reference/index.md` i `docs/adr/README.md` automàticament a cada commit d'Issue o remediació de PR.
- **Linter de Docstrings en CI (`pyproject.toml`, `.github/workflows/ci.yml`)**: Activació de les regles `D` (`pydocstyle` convenció `google`) a Ruff i gate obligatori `--validate-docstrings` a GitHub Actions.

### Fixed
- Moficació invàlida
- Error de repetició de les proves de QA

---

## [0.3.0] - 2026-10-27

### Added
- **Suport Multi-Repositori (`src/services/github_service.py`, `src/utils/config.py`)**: Capacitat de gestionar múltiples repositoris de GitHub mitjançant la variable `GITHUB_REPOS`, descobriment automàtic de repositoris (`list_available_repositories`) i canvi en calent del repositori actiu (`set_active_repository`).
- **Selecció de Repositori al Menú CLI (`src/main.py`)**: Bucle interactiu al menú principal amb visualització permanent del repositori actiu a la capçalera (`📂 REPOSITORI ACTIU`) i nova Opció 1 dedicada a seleccionar el repositori de treball.
- **Gestió de Workflows de GitHub Actions (`src/services/github_service.py`, `src/agents/developer_agent.py`)**: Inclusió de `.github/workflows/*.yml` a l'arbre de sincronització i context del `DeveloperAgent` per permetre crear i mantenir pipelines de desplegament.
- **Automatització del Changelog (`src/utils/changelog_updater.py`, `.github/workflows/changelog.yml`)**: Eina CLI (`ai-changelog`), integració al `DeveloperAgent` i workflow de CI/CD per mantenir `CHANGELOG.md` actualitzat automàticament quan apareixen canvis.
- **Política de Documentació (`docs/Politica_Documentacio.md`)**: Establiment del marc *Docs-as-Code* en 5 nivells per al projecte.

### Changed
- **Workspaces Aïllats per Repositori (`src/agents/developer_agent.py`)**: Els entorns temporals d'execució s'organitzen ara sota `.workspace/<owner__repo>/issue_<num>` i detecten dinàmicament la branca principal del repositori (`get_default_branch`).
- **Documentació de l'Arrel (`README.md`, `.env.example`, `CONTRIBUTING.md`)**: Estandardització del *Quickstart* en menys de 5 minuts, contracte detallat de variables d'entorn amb valors ficticis segurs i mapeig de *Conventional Commits*.

### Security
- **Prevenció de Path Traversal Multi-Repositori (`src/services/github_service.py`, `src/agents/developer_agent.py`)**: Validació estricta del format `owner/repo` (`validate_repo_name`) i verificació `is_relative_to` abans d'escriure qualsevol fitxer dins del workspace aïllat (OWASP Top 10 A01).

---

## [0.2.0] - 2026-10-25

### Added
- **Arquitectura Base d'Agents (`src/agents/base_agent.py`)**: Classe `BaseAgent` amb injecció de dependències (`llm_service`, `github_service`), inicialització *lazy*, càrrega unificada de `docs/code_policy.md` i integració amb `AgentLogger`.
- **Parser JSON Centralitzat (`src/utils/json_parser.py`)**: Mòdul dedicat per a la neteja de blocs Markdown, reparació de cometes triples no escapades, sanejament de seqüències d'escapament invàlides i normalització de respostes d'agents (`pydantic`, `json`, `json-repair`, `yaml`).
- **Configuració Tipada (`src/utils/config.py`)**: Classe immutable `AppConfig` amb validació sota demanda (`validate_github()`, `validate_gemini()`).
- **Eines de Qualitat i CI/CD**: Configuració de `ruff`, `mypy`, `pytest-cov` i punt d'entrada CLI `ai-agent` a `pyproject.toml` (PEP 621), juntament amb matriu Python 3.10/3.11 al workflow `.github/workflows/ci.yml`.

### Changed
- **Refactorització d'Agents (`AnalystAgent`, `DeveloperAgent`, `CodeReviewAgent`)**: Herència des de `BaseAgent`, eliminació de codi duplicat de parsing i descomposició de mètodes llargs seguint el Principi de Responsabilitat Única (SRP).
- **Estandardització de Docstrings i Type Hints**: Unificació de tota la base de codi a docstrings **Google Style (PEP 257)** en català i anotacions de tipus **PEP 484** completes.

### Fixed
- **Correcció de Branca en Remediació (`DeveloperAgent.remediate_pull_request`)**: El workspace aïllat descarrega ara el contingut de la branca de la Pull Request (`ref=branch_name`) en lloc de la branca `main`.
- **Eliminació de Manipulació Manual de `sys.path`**: Supressió de `sys.path.append` a `src/main.py` i ús d'imports canònics `from src...` a tot el projecte.

### Security
- **Aïllament de Secrets en Subprocessos (`DeveloperAgent._build_workspace_env`)**: Filtració de variables sensibles (`GITHUB_TOKEN`, `GEMINI_API_KEY`, `OPENAI_API_KEY`) en l'entorn d'execució de `pytest` dins del workspace i exclusió de `.env` i `logs` durant la còpia local.

---

## [0.1.0] - 2026-03-01

### Added
- Implementació inicial del sistema multi-agent (`AnalystAgent`, `DeveloperAgent`, `CodeReviewAgent`).
- Integració amb l'API de GitHub (`GitHubService`) i Google Gemini (`LLMService`) amb *fallback* automàtic i reintents exponencials (`tenacity`).
- Esquemes Pydantic per a *Structured Outputs* (`src/schemas/agent_schemas.py`).
- Sistema de logging estructurat en format JSON amb rotació automàtica (`src/utils/logger.py`).

### Security
- Mòdul de seguretat per a restabliment de contrasenyes (`src/password_reset.py`) alineat amb OWASP Top 10 i NIST (tokens signats amb HMAC-SHA256, comparació en temps constant, prevenció de TOCTOU i *rate limiting*).
