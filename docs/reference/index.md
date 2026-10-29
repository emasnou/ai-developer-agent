# 📚 Referència Tècnica d'API (Auto-generada)

> **Nota d'automatització (Docs-as-Code):** Aquest document es genera i s'actualitza
> automàticament a partir de l'arbre sintàctic (AST) i dels docstrings Google Style
> del codi font mitjançant `python -m src.utils.doc_updater`.

## 🗺️ Mapa de Mòduls del Sistema (`src/`)

| Mòdul | Fitxer | Responsabilitat Principal | Elements Públics |
| :--- | :--- | :--- | :--- |
| `src.agents.analyst_agent` | [`src/agents/analyst_agent.py`](../../src/agents/analyst_agent.py) | Agent Analista encarregat de transformar requeriments funcionals en una o múltiples Issues de GitHub. | `AnalystAgent` |
| `src.agents.analytics_agent` | [`src/agents/analytics_agent.py`](../../src/agents/analytics_agent.py) | Agent Analític d'IA modular per al processament, inspecció i extracció d'insights de dades. | `AnalyticsValidationError`, `AnalyticsProcessingError`, `AnalyticsAgent` |
| `src.agents.base_agent` | [`src/agents/base_agent.py`](../../src/agents/base_agent.py) | Classe base comuna per a tots els agents d'IA del sistema. | `BaseAgent` |
| `src.agents.code_review_agent` | [`src/agents/code_review_agent.py`](../../src/agents/code_review_agent.py) | Agent CodeReview per auditar la qualitat del codi, el rendiment i la seguretat (OWASP Top 10). | `CodeReviewAgent` |
| `src.agents.developer_agent` | [`src/agents/developer_agent.py`](../../src/agents/developer_agent.py) | Agent Desenvolupador per a la generació, validació amb PyTest i remediació de codi en workspaces aïllats. | `DeveloperAgent` |
| `src.main` | [`src/main.py`](../../src/main.py) | Punt d'entrada de la interfície de línia d'ordres (CLI) per a l'Agent d'IA multi-repositori. | `handle_repository_selection`, `handle_analyst_option`, `handle_developer_option`, `handle_review_option`, `handle_remediation_option`, `main` |
| `src.password_reset` | [`src/password_reset.py`](../../src/password_reset.py) | Mòdul per a la gestió segura del restabliment de contrasenyes. | `TokenValidationError`, `ExpiredTokenError`, `InvalidTokenError`, `PasswordValidationError`, `ResetTokenData`, `PasswordResetTokenManager`, `UserRepository`, `EmailService`, `RateLimiter`, `PasswordResetController`, `validate_email_format`, `validate_password_complexity` |
| `src.prompts.analyst_prompts` | [`src/prompts/analyst_prompts.py`](../../src/prompts/analyst_prompts.py) | Plantilles de prompts de sistema per a l'Agent Analista (`AnalystAgent`). | `build_analyst_system_prompt` |
| `src.prompts.analytics_prompts` | [`src/prompts/analytics_prompts.py`](../../src/prompts/analytics_prompts.py) | Plantilles de prompts de sistema per a l'Agent Analític d'IA (`AnalyticsAgent`). | *(Mòdul de constants)* |
| `src.prompts.developer_prompts` | [`src/prompts/developer_prompts.py`](../../src/prompts/developer_prompts.py) | Plantilles de prompts de sistema, auto-correcció i remediació per a l'Agent Desenvolupador (`DeveloperAgent`). | *(Mòdul de constants)* |
| `src.prompts.review_prompts` | [`src/prompts/review_prompts.py`](../../src/prompts/review_prompts.py) | Plantilles de prompts per a l'auditoria de codi i l'extracció de millores (`CodeReviewAgent`). | *(Mòdul de constants)* |
| `src.schemas.agent_schemas` | [`src/schemas/agent_schemas.py`](../../src/schemas/agent_schemas.py) | Esquemes de dades Pydantic per a les sortides estructurades (Structured Outputs) dels agents. | `FileItem`, `ADRAlternative`, `ArchitectureDecisionRecord`, `DeveloperPlan`, `CodeReviewResponse`, `ImprovementItem`, `ImprovementsResponse`, `AnalystStoryItem`, `AnalystPlan` |
| `src.schemas.analytics_schemas` | [`src/schemas/analytics_schemas.py`](../../src/schemas/analytics_schemas.py) | Esquemes Pydantic per a les consultes i respostes estructurades de l'AnalyticsAgent. | `AnalyticsMetric`, `AnalyticsInsight`, `AnalyticsQuery`, `AnalyticsResponse` |
| `src.schemas.finops_schemas` | [`src/schemas/finops_schemas.py`](../../src/schemas/finops_schemas.py) | Esquemes Pydantic per a la gestió de telemetria de consum de tokens i costos FinOps. | `TokenUsage`, `PricingTier`, `CostBreakdown`, `CallMetricRecord`, `SessionSummary` |
| `src.services.finops_service` | [`src/services/finops_service.py`](../../src/services/finops_service.py) | Servei de catàleg de preus i motor de càlcul de costos FinOps per a models de LLM. | `ModelPricingNotFoundError`, `FinOpsPricingCatalog`, `CostCalculator` |
| `src.services.github_service` | [`src/services/github_service.py`](../../src/services/github_service.py) | Servei d'integració multi-repositori amb l'API de GitHub mitjançant PyGithub. | `GitHubService`, `validate_repo_name` |
| `src.services.llm_service` | [`src/services/llm_service.py`](../../src/services/llm_service.py) | Servei de comunicació resilient amb l'API de Google Gemini. | `LLMService` |
| `src.services.metrics_tracker` | [`src/services/metrics_tracker.py`](../../src/services/metrics_tracker.py) | Servei de telemetria i monitoratge de rendiment, latència i eficiència d'execució d'agents. | `CallTrackingContext`, `MetricsTracker` |
| `src.utils.adr_manager` | [`src/utils/adr_manager.py`](../../src/utils/adr_manager.py) | Mòdul per a la gestió, numeració seqüencial i materialització d'ADRs. | `slugify_title`, `adr_lock`, `get_next_adr_id`, `build_adr_filename`, `materialize_adr_file` |
| `src.utils.changelog_updater` | [`src/utils/changelog_updater.py`](../../src/utils/changelog_updater.py) | Mòdul d'automatització i validació per mantenir actualitzat el fitxer CHANGELOG.md. | `classify_commit_message`, `group_commits_by_category`, `update_changelog_content`, `release_unreleased_content`, `get_recent_git_commits`, `update_changelog_file`, `main` |
| `src.utils.config` | [`src/utils/config.py`](../../src/utils/config.py) | Mòdul de configuració i càrrega segura de variables d'entorn. | `AppConfig`, `parse_repo_list` |
| `src.utils.doc_updater` | [`src/utils/doc_updater.py`](../../src/utils/doc_updater.py) | Motor d'actualització i verificació automàtica de la documentació tècnica (Docs-as-Code). | `ModuleDocInfo`, `AdrEntry`, `inspect_python_module`, `scan_source_modules`, `validate_docstrings_and_types`, `generate_reference_markdown`, `extract_adr_metadata`, `build_adr_index_table`, `sync_adr_index`, `update_all_documentation`, `main` |
| `src.utils.github_templates` | [`src/utils/github_templates.py`](../../src/utils/github_templates.py) | Utilitats per a la càrrega i renderització de les plantilles de GitHub (`.github/`). | `strip_yaml_frontmatter`, `load_github_template`, `render_pull_request_body`, `render_improvement_issue_body` |
| `src.utils.json_parser` | [`src/utils/json_parser.py`](../../src/utils/json_parser.py) | Utilitats centralitzades per a l'extracció, reparació i normalització de respostes JSON/YAML del LLM. | `clean_markdown_fences`, `replace_triple_quoted_strings`, `extract_json_object_bounds`, `sanitize_invalid_escapes`, `normalize_developer_files`, `parse_developer_json_response`, `parse_generic_json_response` |
| `src.utils.logger` | [`src/utils/logger.py`](../../src/utils/logger.py) | Mòdul centralitzat de registre i rotació de logs d'auditoria per als agents. | `JSONFormatter`, `AgentLogger`, `StructuredAgentAdapter` |

---

## 🔍 Especificació Detallada de Mòduls (mkdocstrings)

### `src.agents.analyst_agent`

- **Fitxer font:** [`src/agents/analyst_agent.py`](../../src/agents/analyst_agent.py)
- **Resum:** Agent Analista encarregat de transformar requeriments funcionals en una o múltiples Issues de GitHub.

::: src.agents.analyst_agent

### `src.agents.analytics_agent`

- **Fitxer font:** [`src/agents/analytics_agent.py`](../../src/agents/analytics_agent.py)
- **Resum:** Agent Analític d'IA modular per al processament, inspecció i extracció d'insights de dades.

::: src.agents.analytics_agent

### `src.agents.base_agent`

- **Fitxer font:** [`src/agents/base_agent.py`](../../src/agents/base_agent.py)
- **Resum:** Classe base comuna per a tots els agents d'IA del sistema.

::: src.agents.base_agent

### `src.agents.code_review_agent`

- **Fitxer font:** [`src/agents/code_review_agent.py`](../../src/agents/code_review_agent.py)
- **Resum:** Agent CodeReview per auditar la qualitat del codi, el rendiment i la seguretat (OWASP Top 10).

::: src.agents.code_review_agent

### `src.agents.developer_agent`

- **Fitxer font:** [`src/agents/developer_agent.py`](../../src/agents/developer_agent.py)
- **Resum:** Agent Desenvolupador per a la generació, validació amb PyTest i remediació de codi en workspaces aïllats.

::: src.agents.developer_agent

### `src.main`

- **Fitxer font:** [`src/main.py`](../../src/main.py)
- **Resum:** Punt d'entrada de la interfície de línia d'ordres (CLI) per a l'Agent d'IA multi-repositori.

::: src.main

### `src.password_reset`

- **Fitxer font:** [`src/password_reset.py`](../../src/password_reset.py)
- **Resum:** Mòdul per a la gestió segura del restabliment de contrasenyes.

::: src.password_reset

### `src.prompts.analyst_prompts`

- **Fitxer font:** [`src/prompts/analyst_prompts.py`](../../src/prompts/analyst_prompts.py)
- **Resum:** Plantilles de prompts de sistema per a l'Agent Analista (`AnalystAgent`).

::: src.prompts.analyst_prompts

### `src.prompts.analytics_prompts`

- **Fitxer font:** [`src/prompts/analytics_prompts.py`](../../src/prompts/analytics_prompts.py)
- **Resum:** Plantilles de prompts de sistema per a l'Agent Analític d'IA (`AnalyticsAgent`).

::: src.prompts.analytics_prompts

### `src.prompts.developer_prompts`

- **Fitxer font:** [`src/prompts/developer_prompts.py`](../../src/prompts/developer_prompts.py)
- **Resum:** Plantilles de prompts de sistema, auto-correcció i remediació per a l'Agent Desenvolupador (`DeveloperAgent`).

::: src.prompts.developer_prompts

### `src.prompts.review_prompts`

- **Fitxer font:** [`src/prompts/review_prompts.py`](../../src/prompts/review_prompts.py)
- **Resum:** Plantilles de prompts per a l'auditoria de codi i l'extracció de millores (`CodeReviewAgent`).

::: src.prompts.review_prompts

### `src.schemas.agent_schemas`

- **Fitxer font:** [`src/schemas/agent_schemas.py`](../../src/schemas/agent_schemas.py)
- **Resum:** Esquemes de dades Pydantic per a les sortides estructurades (Structured Outputs) dels agents.

::: src.schemas.agent_schemas

### `src.schemas.analytics_schemas`

- **Fitxer font:** [`src/schemas/analytics_schemas.py`](../../src/schemas/analytics_schemas.py)
- **Resum:** Esquemes Pydantic per a les consultes i respostes estructurades de l'AnalyticsAgent.

::: src.schemas.analytics_schemas

### `src.schemas.finops_schemas`

- **Fitxer font:** [`src/schemas/finops_schemas.py`](../../src/schemas/finops_schemas.py)
- **Resum:** Esquemes Pydantic per a la gestió de telemetria de consum de tokens i costos FinOps.

::: src.schemas.finops_schemas

### `src.services.finops_service`

- **Fitxer font:** [`src/services/finops_service.py`](../../src/services/finops_service.py)
- **Resum:** Servei de catàleg de preus i motor de càlcul de costos FinOps per a models de LLM.

::: src.services.finops_service

### `src.services.github_service`

- **Fitxer font:** [`src/services/github_service.py`](../../src/services/github_service.py)
- **Resum:** Servei d'integració multi-repositori amb l'API de GitHub mitjançant PyGithub.

::: src.services.github_service

### `src.services.llm_service`

- **Fitxer font:** [`src/services/llm_service.py`](../../src/services/llm_service.py)
- **Resum:** Servei de comunicació resilient amb l'API de Google Gemini.

::: src.services.llm_service

### `src.services.metrics_tracker`

- **Fitxer font:** [`src/services/metrics_tracker.py`](../../src/services/metrics_tracker.py)
- **Resum:** Servei de telemetria i monitoratge de rendiment, latència i eficiència d'execució d'agents.

::: src.services.metrics_tracker

### `src.utils.adr_manager`

- **Fitxer font:** [`src/utils/adr_manager.py`](../../src/utils/adr_manager.py)
- **Resum:** Mòdul per a la gestió, numeració seqüencial i materialització d'ADRs.

::: src.utils.adr_manager

### `src.utils.changelog_updater`

- **Fitxer font:** [`src/utils/changelog_updater.py`](../../src/utils/changelog_updater.py)
- **Resum:** Mòdul d'automatització i validació per mantenir actualitzat el fitxer CHANGELOG.md.

::: src.utils.changelog_updater

### `src.utils.config`

- **Fitxer font:** [`src/utils/config.py`](../../src/utils/config.py)
- **Resum:** Mòdul de configuració i càrrega segura de variables d'entorn.

::: src.utils.config

### `src.utils.doc_updater`

- **Fitxer font:** [`src/utils/doc_updater.py`](../../src/utils/doc_updater.py)
- **Resum:** Motor d'actualització i verificació automàtica de la documentació tècnica (Docs-as-Code).

::: src.utils.doc_updater

### `src.utils.github_templates`

- **Fitxer font:** [`src/utils/github_templates.py`](../../src/utils/github_templates.py)
- **Resum:** Utilitats per a la càrrega i renderització de les plantilles de GitHub (`.github/`).

::: src.utils.github_templates

### `src.utils.json_parser`

- **Fitxer font:** [`src/utils/json_parser.py`](../../src/utils/json_parser.py)
- **Resum:** Utilitats centralitzades per a l'extracció, reparació i normalització de respostes JSON/YAML del LLM.

::: src.utils.json_parser

### `src.utils.logger`

- **Fitxer font:** [`src/utils/logger.py`](../../src/utils/logger.py)
- **Resum:** Mòdul centralitzat de registre i rotació de logs d'auditoria per als agents.

::: src.utils.logger
