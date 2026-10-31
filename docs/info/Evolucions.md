Amb la base actual del projecte —que ja disposa d'arquitectura multi-repositori, tres agents especialitzats ([`AnalystAgent`](file:///home/emili/codi/ai-developer-agent/src/agents/analyst_agent.py), [`DeveloperAgent`](file:///home/emili/codi/ai-developer-agent/src/agents/developer_agent.py), [`CodeReviewAgent`](file:///home/emili/codi/ai-developer-agent/src/agents/code_review_agent.py)), validació amb PyTest en workspaces aïllats, *Docs-as-Code* 100% automatitzat i scripts operatius a [`bin/`](file:///home/emili/codi/ai-developer-agent/bin/README.md)—, les noves funcionalitats més interessants es poden agrupar en **6 línies d'evolució d'alt valor**:

---

### 1. 🚀 Mode "Autopilot" (*End-to-End Orchestrator Agent*)
* **Què tenim ara**: Els passos s'executen individualment (Analista $\rightarrow$ Desenvolupador $\rightarrow$ Code Reviewer $\rightarrow$ Remediació).
* **Què aportaria**: Un **`OrchestratorAgent`** (nova opció al menú i a [`bin/ai-agent --action autopilot`](file:///home/emili/codi/ai-developer-agent/bin/ai-agent)) capaç de tancar el cicle complet sense intervenció humana:
  1. Presa una Issue (o un requeriment nou), executa el [`DeveloperAgent`](file:///home/emili/codi/ai-developer-agent/src/agents/developer_agent.py) i obre la Pull Request.
  2. Llança automàticament el [`CodeReviewAgent`](file:///home/emili/codi/ai-developer-agent/src/agents/code_review_agent.py) sobre la PR acabada de crear.
  3. Si l'auditor detecta canvis requerits (`approved = False`), invoca automàticament [`remediate_pull_request`](file:///home/emili/codi/ai-developer-agent/src/agents/developer_agent.py#L583-L678) i torna a auditar (fins a $N$ cicles).
  4. **Auto-reparació de GitHub Actions**: Consulta a través de [`GitHubService`](file:///home/emili/codi/ai-developer-agent/src/services/github_service.py) si el workflow de CI de la PR ha passat en verd a GitHub i, si ha fallat, en descarrega el log per auto-corregir-lo.

---

### 2. 🧠 Indexador Semàntic i Graf de Dependències AST per a Repositoris Grans (`RepoContextIndexer`)
* **Què tenim ara**: [`DeveloperAgent._collect_existing_context`](file:///home/emili/codi/ai-developer-agent/src/agents/developer_agent.py#L84-L115) selecciona els fitxers existents cercant si el seu nom apareix al text de la Issue o agafant els 3 primers fitxers `.py`. En repositoris grans (50+ fitxers), això pot ometre mòduls clau.
* **Què aportaria**:
  * Aprofitar l'anàlisi AST que ja fa [`src/utils/doc_updater.py`](file:///home/emili/codi/ai-developer-agent/src/utils/doc_updater.py) per construir un **mapa d'imports, classes i docstrings** del repositori actiu.
  * Seleccionar automàticament per rellevància semàntica (BM25 o embeddings de Gemini) i per graf d'imports quins fitxers exactes necessita el [`DeveloperAgent`](file:///home/emili/codi/ai-developer-agent/src/agents/developer_agent.py) per resoldre una Issue concreta, reduint el consum de tokens i augmentant la precisió.

---

### 3. 🏛️ Materialització Automàtica d'ADRs des del `DeveloperAgent` (*Quick Win*)
* **Què tenim ara**: A [`src/schemas/agent_schemas.py`](file:///home/emili/codi/ai-developer-agent/src/schemas/agent_schemas.py#L38-L155) ja tenim implementat el model [`ArchitectureDecisionRecord`](file:///home/emili/codi/ai-developer-agent/src/schemas/agent_schemas.py#L38-L143) amb el mètode [`to_markdown()`](file:///home/emili/codi/ai-developer-agent/src/schemas/agent_schemas.py#L87-L143) i el camp opcional `adr` dins de [`DeveloperPlan`](file:///home/emili/codi/ai-developer-agent/src/schemas/agent_schemas.py#L146-L155).
* **Què aportaria**: Connectar-ho dins de [`DeveloperAgent`](file:///home/emili/codi/ai-developer-agent/src/agents/developer_agent.py) perquè, quan el model Gemini prengui una decisió arquitectònica en resoldre una Issue i empleni el camp `adr` del JSON, l'agent generi automàticament el fitxer `docs/adr/NNNN-titol.md`, actualitzi l'índex `docs/adr/README.md` i l'inclogui al commit de la Pull Request.

---

### 4. 📊 Telemetria de Tokens, Costos (FinOps) i Mètriques d'Eficiència (`MetricsTracker`)
* **Què tenim ara**: [`src/utils/logger.py`](file:///home/emili/codi/ai-developer-agent/src/utils/logger.py) registra l'activitat a `logs/agents.log`, però no emmagatzema l'ús de tokens ni les mètriques de rendiment de cada execució.
* **Què aportaria**:
  * Capturar a [`LLMService`](file:///home/emili/codi/ai-developer-agent/src/services/llm_service.py) els comptadors `usage_metadata` de l'SDK de Google GenAI (`prompt_token_count`, `candidates_token_count`), la latència i si s'ha activat el model *fallback*.
  * Un nou comandament `./bin/ai-metrics` (i opció al menú) que mostri estadístiques per repositori: **tokens consumits**, **cost estimat**, **percentatge d'Issues resoltes al 1r intent de PyTest** i **taxa d'aprovació de PRs**.

---

### 5. 🌐 Execució Poliglota per a Repositoris de Diferents Llenguatges (`PolyglotTestRunner`)
* **Què tenim ara**: La gestió de GitHub ja és 100% multi-repositori, però [`DeveloperAgent._run_workspace_tests`](file:///home/emili/codi/ai-developer-agent/src/agents/developer_agent.py#L298-L353) executa sempre `pytest` i `ast.parse` (pensat per a repositoris Python).
* **Què aportaria**: Un detector automàtic d'stack tecnològic al workspace:
  * Si detecta `pyproject.toml` / `requirements.txt` $\rightarrow$ valida amb `pytest`.
  * Si detecta `package.json` (TypeScript / Node / React) $\rightarrow$ valida amb `npm test` / `vitest` / `eslint`.
  * Si detecta `go.mod` (Go) o `Cargo.toml` (Rust) $\rightarrow$ valida amb `go test ./...` o `cargo test`.
  * Això permetria usar el mateix agent per desenvolupar tant repositoris backend en Python com frontends o microserveis en altres llenguatges.

---

### 6. 🐳 Desplegament i Sandbox amb Docker + Mode *Webhook / Event-Driven*
* **Sandbox amb Docker**: Executar els tests del `.workspace/` dins d'un contenidor efímer sense xarxa (`--network none`) per a un aïllament de seguretat total, més el `Dockerfile` i `docker-compose.yml` per desplegar el projecte en qualsevol màquina.
* **Mode Event-Driven (GitHub Webhooks / Polling)**: Que l'agent pugui quedar-se en espera i activar-se sol quan algú etiqueti una Issue a GitHub amb `ai-develop` o obri una nova PR amb `ai-review`.

---

### 🎯 Recomanació de Priorització (Full de Ruta Suggerit)

| Prioritat | Funcionalitat | Complexitat | Impacte Immediat |
| :---: | :--- | :---: | :--- |
| **1** | **Mode "Autopilot" (`OrchestratorAgent`: Issue $\rightarrow$ PR $\rightarrow$ Review $\rightarrow$ Remediació)** | Mitjana | 🔥 Altíssim (autonomia total d'extrem a extrem) |
| **2** | **Materialització automàtica d'ADRs des de `DeveloperPlan` + Telemetria de Tokens/Costos** | Baixa | ⚡ Molt alt (*Quick Win* que completa l'ecosistema actual) |
| **3** | **Desplegament amb `Dockerfile` + `docker-compose.yml` (`bin/ai-deploy`)** | Baixa | 🛡️ Molt alt (llest per producció en qualsevol màquina) |
| **4** | **Indexador Semàntic / Graf AST (`RepoContextIndexer`)** | Mitjana | 🧠 Alt (escalabilitat per a repositoris grans) |

Quina d'aquestes funcionalitats et semblaria més interessant abordar primer?
