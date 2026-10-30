A continuació es detalla una selecció de les 10 eines més consolidades, cobrint codificació, qualitat, seguretat i desplegament.

---

### 1. Cursor

* **Àmbit / Especialització:** Globalista orientat a la fase de desenvolupament (IDE AI-Native).
* **Principals característiques:** *Fork* de VS Code dissenyat des de zero per a fluxos amb LLMs. Indexa el repositori sencer en local i embeddings remots per oferir context de projecte complet, edició multi-fitxer sincronitzada i mode agent integrat a la terminal.
* **Beneficis:** Comprensió holística de l'arquitectura del projecte; redueix dràsticament el canvi de context en tasques de refactorització massiva entre diversos mòduls.
* **Tipus d'ús:** Freemium / Pagament (Subscripció mensual amb quota gratuïta bàsica).

### 2. GitHub Copilot

* **Àmbit / Especialització:** Globalista (Assistència transversal: IDE, Pull Requests, documentació i CLI).
* **Principals característiques:** Integració nativa a l'ecosistema de GitHub (VS Code, JetBrains, Neovim). Autocompletat en temps real, generació de resums de PRs, resolució d'incidències i revisió contextual a nivell d'organització.
* **Beneficis:** Adopció corporativa immediata, compliment d'estàndards empresarials (telemetria i filtres de codi públic) i connexió directa amb plataformes CI/CD.
* **Tipus d'ús:** Pagament (Plans Individuals, Business i Enterprise; gratuït per a estudiants i mantenidors open source destacats).

### 3. Claude Code / Claude Sonnet

* **Àmbit / Especialització:** Globalista d'alta complexitat (Arquitectura, codificació agèntica i CLI autònoma).
* **Principals característiques:** Execució agèntica directament des del terminal capaç de navegar pel repositori, executar proves unitàries, reparar errors de compilació i orquestrar canvis de disseny de sistemes.
* **Beneficis:** Capacitat de raonament i resolució de problemes lògics complexes amb mínima taxa d'al·lucinació respecte a models d'anterior generació; destaca en tasques que requereixen granularitat en repositoris voluminosos.
* **Tipus d'ús:** Pagament (accés mitjançant API per consum de tokens o subscripció).

### 4. Cline (abans Claude Dev)

* **Àmbit / Especialització:** Desenvolupament agèntic i refactorització autònoma a l'editor.
* **Principals característiques:** Extensió autònoma que utilitza eines de terminal, navegador i sistema de fitxers per completar tasques sol·licitades pel desenvolupador de principi a fi, demanant permís humà explícit abans de cada comanda o escriptura.
* **Beneficis:** Suport *Bring-Your-Own-Key* (connectable a qualsevol model com Claude, DeepSeek o models locals via Ollama), transparència de costos pas a pas i control total de les accions de l'agent.
* **Tipus d'ús:** Open Source (Llicència Apache 2.0 / MIT; requereix consum d'API externa o inferència local).

### 5. CodeRabbit

* **Àmbit / Especialització:** Especialitzada en Control de Qualitat i Revisió de Codi (Code Review & QA).
* **Principals característiques:** Agent de revisió de Pull Requests que analitza els canvis línia per línia, detecta antipatrons, avalua l'impacte arquitectònic, suggereix millores en l'estil de codi i genera diagrames de seqüència del PR.
* **Beneficis:** Alleugera el coll d'ampolla dels revisors sènior identificant errors de lògica i regressions abans de la revisió humana; conversa directament als fils de discussió de GitHub/GitLab.
* **Tipus d'ús:** Freemium (Gratuït per a repositoris públics / Pagament per a equips i repositoris privats).

### 6. Qodo (anteriorment CodiumAI)

* **Àmbit / Especialització:** Especialitzada en Control de Qualitat, Verificació i Generació de Tests.
* **Principals característiques:** Motor centrat en la integritat del codi. Analitza el codi font per generar automàticament proves unitàries, tests d'integració, identificar casos límit (*edge cases*) no contemplats i analitzar el comportament del sistema en temps d'execució.
* **Beneficis:** Evita que el desenvolupador generi només proves trivials per augmentar la mètrica de cobertura, forçant la detecció d'escenaris crítics i validació de lògica de negoci.
* **Tipus d'ús:** Freemium / Pagament per a equips corporatius.

### 7. Snyk (Snyk DeepCode AI)

* **Àmbit / Especialització:** Especialitzada en Seguretat d'Aplicacions (DevSecOps: SAST, SCA, secrets i contenidors).
* **Principals característiques:** Detecció estàtica de vulnerabilitats assistida per IA combinada amb regles deterministes de ciberseguretat. No només senyala la fallada, sinó que ofereix automàticament el pegat de correcció (*inline auto-remediation*) que no trenca el codi existent.
* **Beneficis:** Taxa molt baixa de falsos positius respecte a eines SAST tradicionals; garanteix el compliment de normatives (OWASP, CWE) directament a la canonada de CI/CD.
* **Tipus d'ús:** Freemium (Nivell gratuït limitat / Pagament segons volum d'ús i funcionalitats corporatives).

### 8. Semgrep (Semgrep Assistant)

* **Àmbit / Especialització:** Especialitzada en Seguretat de codi i anàlisi estàtica avançada.
* **Principals característiques:** Combina l'anàlisi de codi basat en regles sintàctiques ultraràpides amb IA per validar si una vulnerabilitat potencial és realment explotable segons el flux de dades i el context circumdant.
* **Beneficis:** Redueix massivament la fatiga d'alertes generada pels escàners tradicionals, prioritzant aquelles incidències que realment exposen l'aplicació.
* **Tipus d'ús:** Motor d'escaneig Open Source (LGPL); Semgrep Assistant i mòduls d'equip/IA són de Pagament (SaaS/On-Premise).

### 9. Dynatrace Davis AI / Datadog Watchdog

* **Àmbit / Especialització:** Especialitzada en Desplegament, Operacions i Observabilitat (AIOps & SRE).
* **Principals característiques:** Detecció d'anomalies en temps real en entorns de producció (microserveis, Kubernetes, cues de missatges). Correlaciona automàticament mètriques, traces distribuïdes i registres (*logs*) per dur a terme anàlisis de causa arrel (*Root Cause Analysis*).
* **Beneficis:** Identificació immediata d'un desplegament erroni (*bad rollout*); permet automatitzar polítiques d'*auto-remediation* o activar el *canary rollback* abans que l'usuari final percebi una degradació de servei.
* **Tipus d'ús:** Pagament empresarial (models de llicenciament segons volum de nodes/ingesta de telemetria).

### 10. Northflank / Vercel AI Deployments

* **Àmbit / Especialització:** Especialitzada en Desplegament, Infraestructura i CI/CD modern.
* **Principals característiques:** Plataformes de plataforma com a servei (PaaS) que integren IA per generar la configuració de contenidors (Dockerfiles, manifestos de Kubernetes, xarxes) a partir de l'anàlisi del codi, gestionant desplegaments previsualitzats (*preview environments*) i optimització d'escalabilitat automàtica.
* **Beneficis:** Elimina la càrrega manual de configurar pipelines DevOps complexos; un cop aprovat el codi, la infraestructura s'adapta de forma resilient a la demanda de càrrega.
* **Tipus d'ús:** Freemium / Pagament per consum de recursos d'infraestructura.

---

### Taula resum del cicle de vida

| Eina | Fase principal de l'SDLC | Àmbit | Model de llicència |
| --- | --- | --- | --- |
| **Cursor** | Desenvolupament (IDE) | Globalista | Freemium / Pagament |
| **GitHub Copilot** | Desenvolupament & Col·laboració | Globalista | Pagament comercial |
| **Claude Code** | Disseny, Arquitectura & Codi | Globalista | Pagament (API) |
| **Cline** | Desenvolupament autònom a l'IDE | Globalista | Open Source (eina) + API |
| **CodeRabbit** | Revisió de codi / Pull Requests | Especialitzada (Code Review) | Freemium / Pagament |
| **Qodo** | Qualitat & Generació de Tests | Especialitzada (Testing) | Freemium / Pagament |
| **Snyk** | Seguretat (SAST/SCA/Secrets) | Especialitzada (Seguretat) | Freemium / Pagament |
| **Semgrep** | Seguretat & Compliment de codi | Especialitzada (Seguretat) | Open Core / Pagament |
| **Davis / Watchdog** | Producció & Observabilitat (AIOps) | Especialitzada (SRE/Monitoratge) | Pagament empresarial |
| **Northflank / Vercel** | Desplegament & Infraestructura | Especialitzada (DevOps/PaaS) | Freemium / Pagament |