# 🏛️ Registre de Decisions d'Arquitectura (ADR)

Aquest directori conté els **Architecture Decision Records (ADR)** del projecte **AI Developer Agent**, seguint l'enfocament **Docs-as-Code** i el marc **Diátaxis** definits a [`docs/Politica_Documentacio.md`](../Politica_Documentacio.md) i [`docs/code_policy.md`](../code_policy.md).

Un ADR és un document breu i versionat amb Git que captura una decisió arquitectònica rellevant presa per l'equip d'enginyeria o pels **agents d'IA autònoms** (`AnalystAgent`, `DeveloperAgent`, `CodeReviewAgent`), deixant constància del **context**, el **perquè** de l'elecció, les **alternatives descartades**, l'**impacte de seguretat (OWASP Top 10)** i l'**evidència de verificació amb PyTest**.

---

## 🤖 Com Utilitzen els Agents d'IA els ADRs?

1. **Consulta de Context**: Abans de proposar canvis estructurals en un repositori, els agents consulten les polítiques i els ADRs actius per mantenir la coherència arquitectònica i no reobrir debats ja resolts.
2. **Generació Estructurada d'ADRs**: Quan una Issue o Pull Request implica una decisió d'arquitectura (nou servei, patró de seguretat, canvi en l'aïllament o contractes de dades), l'agent utilitza la plantilla [`0000-template-adr-agent-ia.md`](0000-template-adr-agent-ia.md) i l'esquema Pydantic `ArchitectureDecisionRecord` ([`src/schemas/agent_schemas.py`](../../src/schemas/agent_schemas.py)) per documentar la seva decisió de forma traçable.
3. **Auditoria al Code Review**: El [`CodeReviewAgent`](../../src/agents/code_review_agent.py) verifica que les decisions arquitectòniques respectin els factors de seguretat OWASP i el Principi de Responsabilitat Única (SRP).

---

## 📏 Nomenclatura i Cicle de Vida

* **Format del nom de fitxer**: `NNNN-titol-breu-en-kebab-case.md` (on `NNNN` és un número seqüencial de 4 dígits, ex: `0003-cache-respostes-llm.md`).
* **Estats possibles d'un ADR**:
  * `Proposat`: Generat en una branca `feature/issue-X` pendent d'aprovació a la Pull Request.
  * `Acceptat`: Validat pel pipeline de CI/CD i aprovat al Code Review, vigent a la branca `main`.
  * `Obsolet`: Decisió que ja no aplica perquè la funcionalitat s'ha retirat.
  * `Substituït per ADR-XXXX`: Reemplaçat per una nova decisió arquitectònica posterior (els ADRs antics no s'esborren mai; s'actualitza el seu estat per preservar la traçabilitat històrica).

---

## 📚 Índex d'ADRs del Projecte

<!-- ADR-INDEX-START -->
| ID | Títol de la Decisió | Estat | Data | Autor / Agent IA |
| :--- | :--- | :--- | :--- | :--- |
| **[ADR-0000](0000-template-adr-agent-ia.md)** | **Plantilla Oficial d'ADR per a Agents d'IA i Enginyers** | `Plantilla` | 2026-10-27 | Arquitectura / Docs-as-Code |
| **[ADR-0001](0001-sortides-estructurades-pydantic-i-parser-resilient.md)** | Sortides Estructurades amb Pydantic i Parser Multi-Nivell Resilient | `Acceptat` | 2026-10-25 | `DeveloperAgent` / Equip d'Arquitectura |
| **[ADR-0002](0002-arquitectura-multi-repositori-i-workspaces-aillats.md)** | Gestió Multi-Repositori i Aïllament Segur de Workspaces | `Acceptat` | 2026-10-27 | `DeveloperAgent` / Equip de Seguretat |
<!-- ADR-INDEX-END -->

