"""Agent Analista encarregat de transformar requeriments funcionals en una o múltiples Issues de GitHub."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.prompts.analyst_prompts import build_analyst_system_prompt
from src.schemas.agent_schemas import AnalystPlan, AnalystStoryItem
from src.services.github_service import GitHubService
from src.services.llm_service import LLMService
from src.utils.github_templates import FEATURE_ISSUE_TEMPLATE_REL_PATH
from src.utils.json_parser import parse_generic_json_response


class AnalystAgent(BaseAgent):
    """Agent especialitzat en l'anàlisi funcional, descomposició en Stories seqüencials, BDD i QA."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        github_service: Optional[GitHubService] = None,
        repo_name: Optional[str] = None,
        issue_template_path: Path = Path(FEATURE_ISSUE_TEMPLATE_REL_PATH),
    ) -> None:
        """Inicialitza l'Agent Analista amb els serveis de LLM, GitHub, plantilla i logging.

        Args:
            llm_service: Instància opcional de LLMService per a injecció de dependències.
            github_service: Instància opcional de GitHubService per a injecció de dependències.
            repo_name: Nom opcional del repositori (`owner/repo`) on crear les Issues.
            issue_template_path: Ruta de la plantilla d'Issue de GitHub a aplicar.
        """
        super().__init__(
            agent_name="AnalystAgent",
            llm_service=llm_service,
            github_service=github_service,
            repo_name=repo_name,
        )
        self.issue_template_path: Path = issue_template_path

    @staticmethod
    def _parse_analyst_response(raw_response: str, default_title: str) -> AnalystPlan:
        """Converteix la resposta del LLM (JSON estructurat o Markdown directe) en un `AnalystPlan`.

        Garanteix que les Stories estiguin ordenades seqüencialment (`1..N`) i que cadascuna
        tingui les seves dependències prèvies i resum d'abast tancat definits.

        Args:
            raw_response: Text retornat pel model LLM (JSON `AnalystPlan` o Markdown).
            default_title: Títol base proporcionat per l'usuari.

        Returns:
            AnalystPlan: Pla validat amb una o múltiples Stories ordenades per execució.
        """
        parsed = parse_generic_json_response(raw_response)
        raw_stories = parsed.get("stories") if isinstance(parsed, dict) else None

        if isinstance(raw_stories, list) and raw_stories:
            story_items: list[AnalystStoryItem] = []
            for idx, item in enumerate(raw_stories, start=1):
                if not isinstance(item, dict):
                    continue
                order_val = item.get("execution_order")
                order = int(order_val) if isinstance(order_val, int) and order_val > 0 else idx
                title = str(item.get("title") or default_title).strip() or default_title
                body = str(item.get("body") or "").strip()
                raw_deps = item.get("depends_on_orders")
                deps = (
                    [int(d) for d in raw_deps if isinstance(d, int) and d > 0]
                    if isinstance(raw_deps, list)
                    else []
                )
                deliverable = str(item.get("deliverable_summary") or "").strip()
                story_items.append(
                    AnalystStoryItem(
                        execution_order=order,
                        title=title,
                        body=body,
                        depends_on_orders=deps,
                        deliverable_summary=deliverable,
                    )
                )

            if story_items:
                story_items.sort(key=lambda s: s.execution_order)
                normalized_stories: list[AnalystStoryItem] = []
                order_mapping: dict[int, int] = {}
                for new_idx, story in enumerate(story_items, start=1):
                    order_mapping[story.execution_order] = new_idx

                for new_idx, story in enumerate(story_items, start=1):
                    mapped_deps = sorted(
                        {
                            order_mapping.get(d, d)
                            for d in story.depends_on_orders
                            if order_mapping.get(d, d) < new_idx
                        }
                    )
                    if new_idx > 1 and not mapped_deps:
                        mapped_deps = [new_idx - 1]
                    deliverable = story.deliverable_summary or (
                        f"Lliurable tancat i verificable amb PyTest per al pas {new_idx} "
                        f"({story.title})."
                    )
                    normalized_stories.append(
                        AnalystStoryItem(
                            execution_order=new_idx,
                            title=story.title,
                            body=story.body,
                            depends_on_orders=mapped_deps,
                            deliverable_summary=deliverable,
                        )
                    )

                is_multi = len(normalized_stories) > 1
                rationale = str(parsed.get("decomposition_rationale") or "").strip()
                if not rationale:
                    rationale = (
                        f"El requeriment s'ha dividit en {len(normalized_stories)} Stories "
                        "seqüencials i autocontingudes per assegurar que cada lliurable sigui "
                        "un desenvolupament tancat i verificable sense errors."
                        if is_multi
                        else "El requeriment és atòmic i es pot completar en una única Story tancada."
                    )
                seq_summary = str(parsed.get("execution_sequence_summary") or "").strip()
                if not seq_summary:
                    seq_summary = " -> ".join(
                        f"Pas {s.execution_order}: {s.title}" for s in normalized_stories
                    )
                return AnalystPlan(
                    requires_multiple_stories=is_multi,
                    decomposition_rationale=rationale,
                    execution_sequence_summary=seq_summary,
                    stories=normalized_stories,
                )

        markdown_body = (
            str(parsed.get("body") or parsed.get("markdown") or raw_response).strip()
            if isinstance(parsed, dict)
            else raw_response.strip()
        )
        return AnalystPlan(
            requires_multiple_stories=False,
            decomposition_rationale=(
                "El requeriment és atòmic i es pot implementar i verificar completament "
                "en una única Story autocontinguda."
            ),
            execution_sequence_summary=f"Pas 1: {default_title}",
            stories=[
                AnalystStoryItem(
                    execution_order=1,
                    title=default_title,
                    body=markdown_body,
                    depends_on_orders=[],
                    deliverable_summary=(
                        f"Implementació completa i verificada amb PyTest de '{default_title}'."
                    ),
                )
            ],
        )

    @staticmethod
    def _format_story_title(base_title: str, story_title: str, index: int, total: int) -> str:
        """Formata el títol de la Issue incloent l'ordre seqüencial si hi ha múltiples Stories.

        Args:
            base_title: Títol general introduït per l'usuari.
            story_title: Títol específic de la Story proposat per l'analista.
            index: Posició actual de la Story dins la seqüència (`1..total`).
            total: Nombre total de Stories generades per al requeriment.

        Returns:
            str: Títol formatat per a la Issue de GitHub.
        """
        if total <= 1:
            return base_title.strip() or story_title.strip()

        clean_story = re.sub(
            r"^\[?\s*Story\s+\d+\s*/\s*\d+\s*\]?\s*[:\-]?\s*",
            "",
            story_title.strip(),
            flags=re.IGNORECASE,
        ).strip()
        clean_base = base_title.strip()

        if not clean_story or clean_story.lower() == clean_base.lower():
            return f"[Story {index}/{total}] {clean_base}"
        if clean_base and clean_base.lower() not in clean_story.lower():
            return f"[Story {index}/{total}] {clean_base}: {clean_story}"
        return f"[Story {index}/{total}] {clean_story}"

    @staticmethod
    def _enrich_multi_story_body(
        story: AnalystStoryItem,
        index: int,
        total: int,
        all_stories: list[AnalystStoryItem],
        created_by_order: dict[int, dict[str, Any]],
        rationale: str,
        sequence_summary: str,
    ) -> str:
        """Afegeix al cos de la Issue la secció de traçabilitat i seqüència d'execució.

        Quan un requeriment es descompon en múltiples Stories, documenta dins de cada Issue
        l'ordre d'execució recomanat, les Issues prèvies de les quals depèn i el requisit
        d'execució tancada (sense errors a PyTest).

        Args:
            story: Objecte `AnalystStoryItem` de la Story actual.
            index: Ordre d'execució actual (`1..total`).
            total: Nombre total de Stories del requeriment.
            all_stories: Llista completa de totes les Stories del pla.
            created_by_order: Mapa d'ordres previs (`1..index-1`) a les Issues ja creades a GitHub.
            rationale: Justificació de la divisió en múltiples Stories.
            sequence_summary: Resum de la seqüència recomanada d'execució.

        Returns:
            str: Cos Markdown enriquit per a la Issue de GitHub.
        """
        if total <= 1:
            return story.body

        dep_orders = story.depends_on_orders or ([index - 1] if index > 1 else [])
        dep_labels: list[str] = []
        for dep_order in dep_orders:
            prev_issue = created_by_order.get(dep_order)
            if prev_issue is not None:
                dep_labels.append(f"Issue #{prev_issue['number']} ({prev_issue['title']})")
            else:
                dep_labels.append(f"Story {dep_order}/{total}")

        deps_text = (
            ", ".join(dep_labels)
            if dep_labels
            else "Cap (Primera Story de la seqüència — Base independent)"
        )

        sequence_lines: list[str] = []
        for item in all_stories:
            step_num = item.execution_order
            marker = "👉 **(Aquesta Story)** " if step_num == index else ""
            created = created_by_order.get(step_num)
            issue_ref = f"Issue #{created['number']} — " if created else ""
            sequence_lines.append(f"{step_num}. {marker}{issue_ref}{item.title}")

        sequence_block = "\n".join(sequence_lines)
        deliverable_text = (
            story.deliverable_summary
            or "Lliurable tancat, compilable i amb tests unitaris propis que passen sense errors."
        )

        execution_section = (
            "\n\n---\n"
            "## 🔗 Pla d'Execució Seqüencial i Abast Tancat\n"
            f"- **Ordre d'Execució Recomanat:** Story `{index}` de `{total}` (Executar en el **Pas #{index}**)\n"
            f"- **Dependències Prèvies:** {deps_text}\n"
            f"- **Justificació de la Descomposició:** {rationale}\n"
            f"- **Abast Tancat i Autocontingut (Zero-Breakage):** {deliverable_text}\n"
            "  > ⚠️ ** Directriu per al `DeveloperAgent`:** Aquesta Story s'executa de manera "
            "seqüencial i ha de constituir un desenvolupament tancat que compili i superi tots "
            "els tests de PyTest al 100% sense errors ni referències a codi de Stories futures, "
            "encara que la funcionalitat global es completi en passos posteriors.\n\n"
            "### 🧭 Seqüència Recomanada d'Execució\n"
            f"{sequence_summary}\n\n"
            f"{sequence_block}\n"
        )
        return f"{story.body.rstrip()}{execution_section}"

    @staticmethod
    def _build_recommended_sequence_text(
        execution_sequence: list[dict[str, Any]],
        sequence_summary: str = "",
    ) -> str:
        """Construeix un resum llegible amb l'ordre recomanat d'execució de les Issues creades.

        Args:
            execution_sequence: Llista ordenada de metadades d'execució de cada Story creada.
            sequence_summary: Resum descriptiu opcional de l'ordre d'execució.

        Returns:
            str: Text formatat amb la seqüència pas a pas d'Issues a desenvolupar.
        """
        lines: list[str] = []
        if sequence_summary:
            lines.append(f" Resum de la seqüència: {sequence_summary}")
        for step_info in execution_sequence:
            step = step_info["step"]
            issue_num = step_info["issue_number"]
            title = step_info["title"]
            url = step_info["url"]
            deps = step_info.get("depends_on_issues", [])
            deps_note = (
                f" (executar després de: {', '.join(f'#{d}' for d in deps)})"
                if deps
                else " (inici de la seqüència — sense dependències prèvies)"
            )
            lines.append(f"  {step}. Issue #{issue_num} — {title}{deps_note} -> {url}")
        return "\n".join(lines)

    def analyze_requirement_stories(
        self, requirement: str, issue_title: str
    ) -> AnalystPlan:
        """Analitza un requeriment i determina si cal crear una o múltiples Stories seqüencials.

        Args:
            requirement: Descripció en llenguatge natural de la funcionalitat requerida.
            issue_title: Títol base proposat per a la tasca.

        Returns:
            AnalystPlan: Pla estructurat amb l'avaluació, la seqüència i les Stories resultants.

        Raises:
            Exception: Si es produeix un error durant la consulta al LLM.
        """
        system_prompt = build_analyst_system_prompt(template_path=self.issue_template_path)
        user_prompt = (
            f"Títol de referència: {issue_title}\n\n"
            f"Requeriment funcional a analitzar:\n{requirement}"
        )
        raw_response = self.llm.generate_task_spec(
            user_prompt,
            system_prompt,
            response_schema=AnalystPlan,
        )
        return self._parse_analyst_response(raw_response, default_title=issue_title)

    def process_requirement_and_create_issue(
        self, requirement: str, issue_title: str
    ) -> dict[str, Any]:
        """Analitza el requeriment i publica una o múltiples Issues seqüencials a GitHub.

        Valora si el requeriment es pot resoldre en una sola Story o si cal descompondre'l
        en diverses Stories tancades i executables seqüencialment, tot indicant l'ordre
        recomanat per a la seva execució.

        Args:
            requirement: Descripció en llenguatge natural de la funcionalitat requerida.
            issue_title: Títol base per a la Issue o conjunt d'Issues de GitHub.

        Returns:
            dict[str, Any]: Diccionari amb `number`, `title`, `url` (de la primera Issue),
                `multi_story`, `stories_count`, `decomposition_rationale`,
                `execution_sequence`, `recommended_sequence_text` i la llista `issues`.

        Raises:
            Exception: Si es produeix un error durant la generació del LLM o la crida a GitHub.
        """
        self.logger.info(f"Iniciant anàlisi de requeriment per a la tasca: '{issue_title}'")
        print(
            "🤖 [AnalystAgent] Analitzant requeriments, avaluant descomposició en Stories "
            "i generant matriu de QA amb Gemini..."
        )
        try:
            plan = self.analyze_requirement_stories(requirement, issue_title)
        except Exception as e:
            self.logger.error(f"Error en generar l'especificació amb el LLM: {e}")
            raise

        total_stories = len(plan.stories)
        is_multi = total_stories > 1
        if is_multi:
            self.logger.info(
                f"El requeriment requereix {total_stories} Stories seqüencials: "
                f"{plan.decomposition_rationale}"
            )
            print(
                f"🧩 [AnalystAgent] S'ha determinat crear {total_stories} Stories "
                "seqüencials i autocontingudes."
            )
        else:
            self.logger.info("El requeriment es resoldrà en 1 única Story autocontinguda.")
            print("🤖 [AnalystAgent] Creant la Issue a GitHub...")

        created_issues: list[dict[str, Any]] = []
        created_by_order: dict[int, dict[str, Any]] = {}
        execution_sequence: list[dict[str, Any]] = []

        try:
            for idx, story in enumerate(plan.stories, start=1):
                formatted_title = self._format_story_title(
                    base_title=issue_title,
                    story_title=story.title,
                    index=idx,
                    total=total_stories,
                )
                enriched_body = self._enrich_multi_story_body(
                    story=story,
                    index=idx,
                    total=total_stories,
                    all_stories=plan.stories,
                    created_by_order=created_by_order,
                    rationale=plan.decomposition_rationale,
                    sequence_summary=plan.execution_sequence_summary,
                )
                issue_result = self.github.create_issue(
                    title=formatted_title,
                    body=enriched_body,
                    labels=["enhancement", "agent-analyst"],
                )
                created_issues.append(issue_result)
                created_by_order[idx] = issue_result

                dep_orders = story.depends_on_orders or ([idx - 1] if idx > 1 else [])
                dep_issue_numbers = [
                    created_by_order[d]["number"]
                    for d in dep_orders
                    if d in created_by_order and "number" in created_by_order[d]
                ]
                execution_sequence.append(
                    {
                        "step": idx,
                        "issue_number": issue_result.get("number"),
                        "title": issue_result.get("title", formatted_title),
                        "url": issue_result.get("url"),
                        "depends_on_issues": dep_issue_numbers,
                        "deliverable_summary": story.deliverable_summary,
                    }
                )
                self.logger.info(
                    f"Story {idx}/{total_stories} creada a GitHub: {issue_result.get('url')}"
                )

            recommended_sequence_text = self._build_recommended_sequence_text(
                execution_sequence=execution_sequence,
                sequence_summary=plan.execution_sequence_summary,
            )
            if is_multi:
                self.logger.info(
                    f"Seqüència d'execució recomanada:\n{recommended_sequence_text}"
                )

            first_issue = created_issues[0]
            return {
                "number": first_issue.get("number"),
                "title": first_issue.get("title"),
                "url": first_issue.get("url"),
                "multi_story": is_multi,
                "stories_count": total_stories,
                "decomposition_rationale": plan.decomposition_rationale,
                "execution_sequence_summary": plan.execution_sequence_summary,
                "execution_sequence": execution_sequence,
                "recommended_sequence_text": recommended_sequence_text,
                "issues": created_issues,
            }
        except Exception as e:
            self.logger.error(f"Error en publicar les Issues a GitHub: {e}")
            raise

