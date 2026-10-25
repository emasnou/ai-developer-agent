"""Punt d'entrada de la interfície de línia d'ordres (CLI) per a l'Agent d'IA."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Afegir el directori arrel al sys.path per compatibilitat d'execució directa
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.analyst_agent import AnalystAgent
from src.agents.code_review_agent import CodeReviewAgent
from src.agents.developer_agent import DeveloperAgent
from src.services.github_service import GitHubService


def _prompt_non_empty(prompt_text: str, empty_warning: str) -> str:
    """Sol·licita una entrada a l'usuari fins que introdueixi un text no buit.

    Args:
        prompt_text: Text que es mostra a l'usuari per demanar la dada.
        empty_warning: Missatge d'avís si l'usuari deixa el camp en blanc.

    Returns:
        str: Text validat sense espais sobrants als extrems.
    """
    value = input(prompt_text).strip()
    while not value:
        print(empty_warning)
        value = input(prompt_text).strip()
    return value


def _select_open_pull_request(github_service: GitHubService, action_label: str) -> Optional[int]:
    """Mostra les Pull Requests obertes i demana a l'usuari que en seleccioni una.

    Args:
        github_service: Instància activa de GitHubService.
        action_label: Verb descriptiu de l'acció ('auditar' o 'remediar').

    Returns:
        Optional[int]: Número de la PR seleccionada o None si es cancel·la o no n'hi ha.
    """
    prs = github_service.get_pull_requests()
    if not prs:
        print(f"ℹ️ No hi ha cap Pull Request oberta pendent de {action_label}.")
        return None

    print("\n📋 Pull Requests obertes a GitHub:\n")
    pr_dict: dict[int, Any] = {}
    for pr in prs:
        pr_dict[pr.number] = pr
        print(f"  [#{pr.number}] - {pr.title} (Branca: {pr.head.ref})")

    user_input = input(f"\n📌 Introdueix el número de la PR a {action_label} (o 'q' per eixir): ").strip()
    if user_input.lower() == "q" or not user_input.isdigit():
        return None

    pr_num = int(user_input)
    if pr_num not in pr_dict:
        print(f"⚠️ La PR #{pr_num} no existeix a la llista.")
        return None
    return pr_num


def handle_analyst_option() -> None:
    """Executa el flux interactiu de l'Agent Analista (Opció 1)."""
    print("\n--- 📝 NOU REQUERIMENT PER A L'AGENT ANALISTA ---")
    issue_title = _prompt_non_empty("📌 Títol de la tasca: ", "⚠️ El títol no pot estar buit.")

    print("\n📝 Descriu el requeriment o funcionalitat que vols crear:")
    user_requirement = _prompt_non_empty("> ", "⚠️ El requeriment no pot estar buit.")

    try:
        analyst = AnalystAgent()
        resultat = analyst.process_requirement_and_create_issue(user_requirement, issue_title)
        print(f"\n✅ Issue creada amb èxit a: {resultat['url']}")
    except Exception as e:
        print(f"\n❌ Error durant el procés de creació de la Issue: {e}")


def handle_developer_option() -> None:
    """Executa el flux interactiu de l'Agent Desenvolupador (Opció 2)."""
    print("\n--- 🛠️ DESENVOLUPAMENT DE TASQUES AMB L'AGENT DESENVOLUPADOR ---")
    try:
        github_service = GitHubService()
        open_issues = github_service.get_open_issues()
        if not open_issues:
            print("ℹ️ No hi ha cap Issue oberta pendent de desenvolupament al repositori.")
            return

        print("\n📋 Llista de les Issues obertes a GitHub:\n")
        issues_dict = {issue.number: issue for issue in open_issues}
        for issue in open_issues:
            print(f"  [#{issue.number}] - {issue.title}")

        selected_issue_number: Optional[int] = None
        while selected_issue_number is None:
            user_input = input(
                "\n📌 Introdueix el número (ID) de la Issue que vols desenvolupar (o 'q' per eixir): "
            ).strip()
            if user_input.lower() == "q":
                print("Operació cancel·lada.")
                return
            if not user_input.isdigit():
                print("⚠️ Entrada no vàlida. Si us plau, introdueix un número de la llista.")
                continue
            num = int(user_input)
            if num not in issues_dict:
                print(f"⚠️ El número #{num} no correspon a cap Issue oberta de la llista.")
                continue
            selected_issue_number = num

        developer = DeveloperAgent(github_service=github_service)
        resultat = developer.develop_and_test(issue_number=selected_issue_number)
        if resultat["success"]:
            print(f"\n🎉 Desenvolupament completat amb èxit en {resultat['attempts']} intent(s)!")
        else:
            print("\n⚠️ No s'ha pogut completar el desenvolupament de manera autònoma.")
    except Exception as e:
        print(f"\n❌ S'ha produït un error en recuperar o processar la tasca: {e}")


def handle_review_option() -> None:
    """Executa el flux interactiu de l'Agent Auditor de Codi (Opció 3)."""
    print("\n--- 🔍 AUDITORIA DE CODI I SEGURETAT (CODE REVIEW) ---")
    try:
        github_service = GitHubService()
        pr_num = _select_open_pull_request(github_service, "auditar")
        if pr_num is None:
            return

        reviewer = CodeReviewAgent(github_service=github_service)
        resultat = reviewer.review_pull_request(pr_number=pr_num)

        print("\n" + "=" * 60)
        print(resultat["report"])
        print("=" * 60)

        if resultat["approved"]:
            print("\n🎉 La Pull Request ha estat APROVADA!")
            created_issues = reviewer.create_future_improvement_issues(
                pr_number=pr_num,
                review_report=resultat["report"],
            )
            if created_issues:
                print(
                    f"\n✅ S'han creat {len(created_issues)} Issue(s) de millora futura "
                    "amb l'etiqueta 'enhancement':"
                )
                for iss in created_issues:
                    print(f"  - [{iss['title']}] ({iss['url']})")
            else:
                print("ℹ️ No s'han trobat millores addicionals a registrar.")
    except Exception as e:
        print(f"❌ Error durant el procés de Code Review: {e}")


def handle_remediation_option() -> None:
    """Executa el flux interactiu de Remediació segons el Code Review (Opció 4)."""
    print("\n--- 🛠️ REMEDIACIÓ I REFACTORITZACIÓ SEGONS CODE REVIEW ---")
    try:
        github_service = GitHubService()
        pr_num = _select_open_pull_request(github_service, "remediar")
        if pr_num is None:
            return

        developer = DeveloperAgent(github_service=github_service)
        resultat = developer.remediate_pull_request(pr_number=pr_num)

        if resultat["success"]:
            print(f"\n🎉 Remediació completada i pujada a la branca de la PR #{pr_num}!")
            print("💡 Ara pots tornar a executar l'Opció 3 per validar que la nova revisió sigui APROVADA.")
        else:
            print("\n⚠️ No s'ha pogut completar el procés de remediació autònoma.")
    except Exception as e:
        print(f"❌ Error durant el procés de remediació: {e}")


def main() -> None:
    """Mostra el menú principal interactiu i despatxa l'opció seleccionada."""
    print("=" * 60)
    print("🤖 AGENT D'IA PER A DESENVOLUPAMENT AUTÒNOM DE PROGRAMARI")
    print("=" * 60)
    print("1. [Analista] Crear una nova Issue a GitHub des d'un requeriment")
    print("2. [Desenvolupador] Desenvolupar i provar una Issue de GitHub")
    print("3. [Code Reviewer] Auditar una Pull Request (Nomenclatura + OWASP Top 10)")
    print("4. [Remediació] Refactoritzar i corregir una PR segons el Code Review")
    print("5. Sortir")

    opcio = input("\nSelecciona una opció (1/2/3/4/5): ").strip()

    if opcio.lower() == "q" or opcio == "5":
        print("\nFins aviat! 👋")
        return

    handlers = {
        "1": handle_analyst_option,
        "2": handle_developer_option,
        "3": handle_review_option,
        "4": handle_remediation_option,
    }

    handler = handlers.get(opcio)
    if handler is None:
        print("\n❌ Error: Opció no vàlida. Has de seleccionar 1, 2, 3, 4 o 5.")
        return

    handler()


if __name__ == "__main__":
    main()

