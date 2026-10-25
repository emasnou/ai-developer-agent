# 📦 Historial de Canvis (CHANGELOG)

Tots els canvis rellevants d'aquest projecte es documenten en aquest fitxer.
El format es basa en [Keep a Changelog](https://keepachangelog.com/ca/1.1.0/) i el projecte segueix [Semantic Versioning](https://semver.org/lang/ca/).

---

## [0.2.0] - 2026-10-25

### Afegit
- **Arquitectura Base d'Agents (`src/agents/base_agent.py`)**: Nova classe abstracta `BaseAgent` amb suport d'injecció de dependències (`llm_service`, `github_service`), inicialització *lazy*, càrrega unificada de `docs/code_policy.md` i integració amb `AgentLogger`.
- **Parser JSON Centralitzat (`src/utils/json_parser.py`)**: Mòdul dedicat per a la neteja de blocs Markdown, reparació de cometes triples no escapades, sanejament de seqüències d'escapament invàlides i normalització de respostes d'agents amb suport multi-nivell (`pydantic`, `json`, `json-repair`, `yaml`).
- **Configuració Tipada (`src/utils/config.py`)**: Classe immutable `AppConfig` amb validació sota demanda (`validate_github()`, `validate_gemini()`) que permet importar mòduls en tests unitaris sense requerir un fitxer `.env` actiu.
- **Documentació de Governança**: Creació de [`CONTRIBUTING.md`](CONTRIBUTING.md) i [`CHANGELOG.md`](CHANGELOG.md), i actualització integral de [`README.md`](README.md) i [`docs/code_policy.md`](docs/code_policy.md).
- **Eines de Qualitat i CI/CD**: Configuració de `ruff`, `mypy`, `pytest-cov` i punt d'entrada CLI `ai-agent` a [`pyproject.toml`](pyproject.toml) (estàndard PEP 621), juntament amb matriu Python 3.10/3.11 al workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

### Modificat
- **Refactorització d'Agents (`AnalystAgent`, `DeveloperAgent`, `CodeReviewAgent`)**: Herència des de `BaseAgent`, eliminació de codi duplicat de parsing i descomposició de mètodes llargs seguint el Principi de Responsabilitat Única (SRP).
- **Modularització de la CLI (`src/main.py`)**: Separació del bucle principal en gestors independents per a cada opció del menú (`handle_analyst_option`, `handle_developer_option`, `handle_review_option`, `handle_remediation_option`).
- **Estandardització de Docstrings i Type Hints**: Unificació de tota la base de codi a docstrings **Google Style (PEP 257)** en català i anotacions de tipus **PEP 484** completes.

### Corregit
- **Correcció de Branca en Remediació (`DeveloperAgent.remediate_pull_request`)**: El workspace aïllat ara descarrega el contingut de la branca de la Pull Request (`ref=branch_name`) en lloc de la branca `main`, evitant la pèrdua dels canvis previs de la PR.
- **Aïllament de Secrets en Subprocessos (`DeveloperAgent._build_workspace_env`)**: Sanejament de variables sensibles (`GITHUB_TOKEN`, `GEMINI_API_KEY`, `OPENAI_API_KEY`) en l'entorn d'execució de `pytest` dins del workspace i exclusió de `.env` i `logs` durant la còpia local.
- **Dependències**: Afegida la llibreria `json-repair` a `requirements.txt` i `pyproject.toml`, i eliminada la variable obsoleta `OPENAI_API_KEY` de `.env.example`.

---

## [0.1.0] - 2026-03-01

### Afegit
- Implementació inicial del sistema multi-agent (`AnalystAgent`, `DeveloperAgent`, `CodeReviewAgent`).
- Integració amb l'API de GitHub (`GitHubService`) i Google Gemini (`LLMService`) amb *fallback* automàtic i reintents exponencials (`tenacity`).
- Esquemes Pydantic per a *Structured Outputs* (`src/schemas/agent_schemas.py`).
- Mòdul de seguretat per a restabliment de contrasenyes (`src/password_reset.py`) alineat amb OWASP Top 10 i NIST.
- Sistema de logging estructurat en format JSON amb rotació automàtica (`src/utils/logger.py`).

