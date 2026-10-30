**arquitectura multi-agent autònoma (Agentic Lifecycle)**.
Cada etapa està governada per un agent especialitzat que orquestra crides a LLMs (amb prompts de sistema optimitzats, eines de context i accés a APIs externes), incorporant punts de control estratègics **Human-in-the-Loop (HITL)** on la validació o correcció humana és imprescindible abans d'avançar.

---

### Arquitectura agèntica d'extrem a extrem

```
[ Requeriments de Negoci / Veu del Client ]
                 │
                 ▼
 ┌───────────────────────────────────────────────┐
 │ AGENT 1: Product Architect Agent              │
 │ (Anàlisi de necessitats, regles de negoci)    │
 └──────────────────────┬────────────────────────┘
                        │
                        ▼
             [ HITL 1: Validació PM ] ────(Retorn / Esmena)
                        │ (Aprovat)
                        ▼
 ┌───────────────────────────────────────────────┐
 │ AGENT 2: Agile Storyteller Agent              │
 │ (Desglossament: Epics, User Stories, Gherkin) │
 └──────────────────────┬────────────────────────┘
                        │
                        ▼
 ┌───────────────────────────────────────────────┐
 │ AGENT 3: Software Engineer Agent              │
 │ (Context repo, TDD, generació de branques)    │
 └──────────────────────┬────────────────────────┘
                        │
                        ▼
 ┌───────────────────────────────────────────────┐
 │ AGENT 4: QA & Mutation Test Agent             │
 │ (Generació i execució de tests, edge cases)   │
 └──────────────────────┬────────────────────────┘
                        │
                        ▼
 ┌───────────────────────────────────────────────┐
 │ AGENT 5: Security & Governance Agent          │
 │ (SAST/SCA agèntic, correcció de CVEs)         │
 └──────────────────────┬────────────────────────┘
                        │
                        ▼
 ┌───────────────────────────────────────────────┐
 │ AGENT 6: Code Review & Gatekeeper Agent       │
 │ (Avaluació de PR, qualitat i arquitectura)    │
 └──────────────────────┬────────────────────────┘
                        │
                        ▼
            [ HITL 2: Validació Tech Lead ] ────(Rebuig / Canvis)
                        │ (Merge a main)
                        ▼
 ┌───────────────────────────────────────────────┐
 │ AGENT 7: DevOps & Deployment Agent            │
 │ (CI/CD, build OCI, orquestració Canary)       │
 └──────────────────────┬────────────────────────┘
                        │
                        ▼
 ┌───────────────────────────────────────────────┐
 │ AGENT 8: SRE & Observability Agent            │
 │ (AIOps, detecció d'anomalies i auto-rollback) │
 └──────────────────────┬────────────────────────┘
                        │ (Anomalia greu)
                        ▼
            [ HITL 3: Notificació Incident ]

```

---

### Detall dels Agents i Cicles de Decisió

#### 1. Presa de Requeriments: `Product Architect Agent`

* **Model LLM:** Raonament profund (o1 / Claude 3.7 Sonnet thinking).
* **Funció:** Ingesta transcripcions de reunions amb clients, documents funcionals en brut o tiquets d'incidències. Extreu dependències de negoci, incongruències funcionals i riscos no tècnics.
* **Outputs:** Document de Requeriments de Producte (PRD) estructurat amb límits d'abast clars.
* **🚨 PUNT DE CONTROL HITL 1 (Product Manager / Stakeholder):**
* El PM revisa el PRD sintetitzat.
* Si hi ha buits de negoci o supòsits erronis, el PM afegeix notes o rectifica criteris directament a la interfície (Jira/Linear/Notion). L'agent reajusta el PRD abans de passar a la fase següent.



#### 2. Definició i Refinament: `Agile Storyteller Agent`

* **Model LLM:** LLM orientat a instruccions riquides i format estructurat (Claude Sonnet / GPT-4o).
* **Funció:** Transforma el PRD aprovat en User Stories atòmiques. Per a cada tasca defineix:
* Descripció en format estàndard (*Com a... vull... per tal de...*).
* Criteris d'acceptació redactats en sintaxi formal **Gherkin / BDD** (`Given-When-Then`).
* Estimació de complexitat i càrrega de context necessària del repositori.


* **Outputs:** Tiquets creats a Jira, Linear o GitHub Issues llestos per a desenvolupament.

#### 3. Desenvolupament Autònom: `Software Engineer Agent`

* **Model LLM:** Model altament especialitzat en codificació i context ampli (Claude 3.7 Sonnet / Cursor Agent / DeepSeek-V3).
* **Funció:**
* Llegeix el tiquet i clona la branca del repositori.
* Indexa el codi existent (via vector store / tree-sitter AST) per respectar patrons de disseny, convenis i tipus.
* Segueix cicle TDD: redacta primer els tests associats al Gherkin i després implementa el codi font necessari per fer-los passar.
* Fa commits atòmics amb missatges semàntics (*Conventional Commits*) i obre una Pull Request en estat *Draft*.



#### 4. Control de Qualitat: `QA & Mutation Test Agent`

* **Model LLM:** Qodo (CodiumAI) / Test-focused LLM pipelines.
* **Funció:**
* Analitza el diff del codi i genera proves de mutació, estrès i casos extrems (*null pointers*, desbordaments, fallades d'API remota).
* Executa la suite de proves en un contenidor efímer. Si falla, obre un diàleg agèntic amb l'Agent Desenvolupador enviant els logs de l'error per tal que auto-corregir el bug de forma iterativa (fins a un màxim de 3 intents autònoms).



#### 5. Seguretat Predictiva: `Security & Governance Agent`

* **Model LLM:** Semgrep Assistant / Snyk DeepCode AI.
* **Funció:**
* Executa anàlisi estàtica (SAST) i comprovació de dependències (SCA).
* Un LLM actua de jutge de context: avalua si una funció aparentment vulnerable té filtres prèvis o està exposada a la xarxa externa.
* Si detecta un secret commitejat o una injecció SQL, l'agent atura el flux i fa un push amb el pedaç (*auto-remediation*) directament a la branca.



#### 6. Avaluació de Pull Request: `Code Review & Gatekeeper Agent`

* **Model LLM:** CodeRabbit / PR-Reviewer agèntic.
* **Funció:**
* Avalua la neteja arquitectònica, duplicitat de lògica, cobertura total i eficiència algorítmica.
* Comenta directament línia per línia al PR amb suggeriments interactius i resumeix l'impacte global del canvi.


* **🚨 PUNT DE CONTROL HITL 2 (Tech Lead / Senior Developer):**
* La intervenció humana és obligatòria per fer el **Merge a `main**`.
* El desenvolupador sènior avalua la síntesi de l'Agent Revisor, inspecciona el diff crític i, o bé aprova la unió, o bé respon als comentaris del bot demanant canvis arquitectònics (l'Agent Desenvolupador s'activa de nou per aplicar les correccions sol·licitades pel Tech Lead).



#### 7. Desplegament i Infraestructura: `DevOps & Deployment Agent`

* **Model LLM:** LLM especialitzat en manifestos IaC (Terraform, Kubernetes, Docker).
* **Funció:**
* Un cop fet el merge, construeix la imatge de contenidor i verifica la integritat criptogràfica (Cosign).
* Configura el pla de desplegament Canary (ex. 10% de trànsit inicial via Istio / Argo Rollouts) i genera el manifest d'infraestructura actualitzat.
* Executa el rollout progressiu en producció.



#### 8. Operacions i Resiliència: `SRE & Observability Agent`

* **Model LLM:** Datadog Watchdog / Dynatrace Davis AIOps Engine.
* **Funció:**
* Supervisa mètriques clau (latència p99, taxa d'error 5xx, ús de CPU/memòria, volum de logs inusuals).
* **Auto-Rollback autònom:** Si detecta degradació superior als llindars preestablerts durant la finestra Canary, commuta immediatament el 100% del trànsit a la versió anterior sense intervenció humana.


* **🚨 PUNT DE CONTROL HITL 3 (SRE / On-Call Engineer - Post-Incident):**
* Si s'ha produït un rollback o anomalia, l'agent redacta un esborrany d'anàlisi post-mortem (RCA) correlacionant el commit causant amb els registres del sistema.
* L'enginyer de guàrdia valida l'informe, aprova la creació automàtica del tiquet de bug al backlog i coordina les accions correctives amb el *Product Architect Agent*.



---

### Matriu de Responsabilitats i Rols dels Agents

| Fase | Agent Responsable | Models / Motors de Suport | Decisió Autònoma vs Humana |
| --- | --- | --- | --- |
| **Requeriments** | `Product Architect Agent` | Claude 3.7 Sonnet / o1 | **HITL 1:** Aprovació del PRD pel Product Manager |
| **Stories & BDD** | `Agile Storyteller Agent` | GPT-4o / Claude Sonnet | **Autònoma:** Generació i càrrega a Jira/Linear |
| **Codificació** | `Software Engineer Agent` | Claude Code / Cursor Agent | **Autònoma:** TDD i commits a branca de treball |
| **QA / Tests** | `QA & Mutation Test Agent` | Qodo / Pytest / Jest | **Autònoma:** Cicle iteratiu de resolució de bugs |
| **Seguretat** | `Security Agent` | Semgrep / Snyk DeepCode | **Autònoma:** Filtrat de falsos positius i pedaços |
| **Revisió Codi** | `Gatekeeper Agent` | CodeRabbit | **HITL 2:** Aprovació del PR pel Tech Lead per merge |
| **Desplegament** | `DevOps Agent` | ArgoCD / GitHub Actions | **Autònoma:** Build i obertura de Canary (10%) |
| **Producció** | `SRE Observability Agent` | Datadog / Dynatrace | **Autònoma (Rollback)** + **HITL 3 (Validació Post-Mortem)** |