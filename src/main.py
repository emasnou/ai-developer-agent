"""Punt d'entrada de la interfície de línia d'ordres (CLI) per a l'Agent d'IA multi-repositori."""

from __future__ import annotations

from typing import Any, Callable, Optional

from src.agents.analyst_agent import AnalystAgent
from src.agents.code_review_agent import CodeReviewAgent
from src.agents.developer_agent import DeveloperAgent
from src.services.github_service import GitHubService
from src.utils.config import GITHUB_REPO


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


def _get_or_init_github_service(
    github_service: Optional[GitHubService], require_repo: bool = False
) -> GitHubService:
    """Retorna la instància de GitHubService proporcionada o n'inicialitza una de nova.

    Args:
        github_service: Instància opcional ja inicialitzada.
        require_repo: Si cal exigir un repositori actiu immediatament.

    Returns:
        GitHubService: Instància preparada del servei de GitHub.
    """
    if github_service is not None:
        return github_service
    return GitHubService(repo_name=GITHUB_REPO, require_repo=require_repo)


def _ensure_active_repository(github_service: GitHubService) -> bool:
    """Verifica que hi hagi un repositori seleccionat o demana triar-ne un.

    Args:
        github_service: Instància activa de GitHubService.

    Returns:
        bool: True si hi ha un repositori actiu vàlid, False en cas contrari.
    """
    if github_service.active_repo_name:
        return True
    print("\n⚠️ No hi ha cap repositori de GitHub seleccionat actualment.")
    selected = handle_repository_selection(github_service)
    return selected is not None


def _select_open_pull_request(github_service: GitHubService, action_label: str) -> Optional[int]:
    """Mostra les Pull Requests obertes del repositori actiu i en demana la selecció.

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

    print(f"\n📋 Pull Requests obertes a '{github_service.active_repo_name}':\n")
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


def _resolve_repo_choice(user_choice: str, available_repos: list[str]) -> Optional[str]:
    """Converteix l'entrada de l'usuari (índex numèric o nom `owner/repo`) en un repositori.

    Args:
        user_choice: Text introduït per l'usuari.
        available_repos: Llista de repositoris disponibles mostrats per pantalla.

    Returns:
        Optional[str]: Nom del repositori (`owner/repo`) o None si l'índex és fora de rang.
    """
    if user_choice.isdigit():
        idx = int(user_choice)
        if 1 <= idx <= len(available_repos):
            return available_repos[idx - 1]
        return None
    return user_choice


def handle_repository_selection(
    github_service: Optional[GitHubService] = None,
) -> Optional[str]:
    """Mostra la llista de repositoris disponibles i permet seleccionar el repositori actiu.

    Args:
        github_service: Instància compartida de GitHubService on activar el repositori.

    Returns:
        Optional[str]: Nom del repositori seleccionat (`owner/repo`) o None si es cancel·la.
    """
    print("\n--- 📂 SELECCIÓ DEL REPOSITORI DE GITHUB ---")
    try:
        service = _get_or_init_github_service(github_service, require_repo=False)
        available_repos = service.list_available_repositories()

        if available_repos:
            print("\n📋 Repositoris de GitHub disponibles:\n")
            for idx, repo_name in enumerate(available_repos, start=1):
                active_marker = " (actiu)" if repo_name == service.active_repo_name else ""
                print(f"  [{idx}] {repo_name}{active_marker}")
        else:
            print("ℹ️ No s'han trobat repositoris preconfigurats; pots introduir 'owner/repo'.")

        choice = input(
            "\n📌 Selecciona el número del repositori o escriu 'owner/repo' (o 'q' per cancel·lar): "
        ).strip()
        if not choice or choice.lower() == "q":
            print("Selecció de repositori cancel·lada.")
            return service.active_repo_name

        target_repo = _resolve_repo_choice(choice, available_repos)
        if target_repo is None:
            print("⚠️ Número de repositori fora de rang.")
            return service.active_repo_name

        selected = service.set_active_repository(target_repo)
        print(f"\n✅ Repositori actiu seleccionat: {selected}")
        return selected
    except Exception as e:
        print(f"\n❌ Error en seleccionar el repositori: {e}")
        return None


def handle_analyst_option(github_service: Optional[GitHubService] = None) -> None:
    """Executa el flux interactiu de l'Agent Analista sobre el repositori actiu."""
    print("\n--- 📝 NOU REQUERIMENT PER A L'AGENT ANALISTA ---")
    try:
        service = _get_or_init_github_service(github_service, require_repo=False)
        if not _ensure_active_repository(service):
            return

        print(f"📂 Repositori de treball: {service.active_repo_name}")
        issue_title = _prompt_non_empty("📌 Títol de la tasca: ", "⚠️ El títol no pot estar buit.")
        print("\n📝 Descriu el requeriment o funcionalitat que vols crear:")
        user_requirement = _prompt_non_empty("> ", "⚠️ El requeriment no pot estar buit.")

        analyst = AnalystAgent(github_service=service, repo_name=service.active_repo_name)
        resultat = analyst.process_requirement_and_create_issue(user_requirement, issue_title)
        print(f"\n✅ Issue creada amb èxit a '{service.active_repo_name}': {resultat['url']}")
    except Exception as e:
        print(f"\n❌ Error durant el procés de creació de la Issue: {e}")


def _prompt_issue_selection(open_issues: list[Any], repo_name: Optional[str]) -> Optional[int]:
    """Mostra les Issues obertes i demana a l'usuari seleccionar-ne una per ID.

    Args:
        open_issues: Llista d'objectes Issue oberts al repositori.
        repo_name: Nom del repositori actiu.

    Returns:
        Optional[int]: Número de la Issue escollida o None si l'usuari cancel·la.
    """
    print(f"\n📋 Llista de les Issues obertes a '{repo_name}':\n")
    issues_dict = {issue.number: issue for issue in open_issues}
    for issue in open_issues:
        print(f"  [#{issue.number}] - {issue.title}")

    while True:
        user_input = input(
            "\n📌 Introdueix el número (ID) de la Issue que vols desenvolupar (o 'q' per eixir): "
        ).strip()
        if user_input.lower() == "q":
            print("Operació cancel·lada.")
            return None
        if not user_input.isdigit():
            print("⚠️ Entrada no vàlida. Si us plau, introdueix un número de la llista.")
            continue
        num = int(user_input)
        if num not in issues_dict:
            print(f"⚠️ El número #{num} no correspon a cap Issue oberta de la llista.")
            continue
        return num


def handle_developer_option(github_service: Optional[GitHubService] = None) -> None:
    """Executa el flux interactiu de l'Agent Desenvolupador sobre el repositori actiu."""
    print("\n--- 🛠️ DESENVOLUPAMENT DE TASQUES AMB L'AGENT DESENVOLUPADOR ---")
    try:
        service = _get_or_init_github_service(github_service, require_repo=False)
        if not _ensure_active_repository(service):
            return

        print(f"📂 Repositori de treball: {service.active_repo_name}")
        open_issues = service.get_open_issues()
        if not open_issues:
            print("ℹ️ No hi ha cap Issue oberta pendent de desenvolupament al repositori.")
            return

        selected_issue_number = _prompt_issue_selection(open_issues, service.active_repo_name)
        if selected_issue_number is None:
            return

        developer = DeveloperAgent(github_service=service, repo_name=service.active_repo_name)
        resultat = developer.develop_and_test(issue_number=selected_issue_number)
        if resultat["success"]:
            print(f"\n🎉 Desenvolupament completat amb èxit en {resultat['attempts']} intent(s)!")
        else:
            print("\n⚠️ No s'ha pogut completar el desenvolupament de manera autònoma.")
    except Exception as e:
        print(f"\n❌ S'ha produït un error en recuperar o processar la tasca: {e}")


def handle_review_option(github_service: Optional[GitHubService] = None) -> None:
    """Executa el flux interactiu de l'Agent Auditor de Codi sobre el repositori actiu."""
    print("\n--- 🔍 AUDITORIA DE CODI I SEGURETAT (CODE REVIEW) ---")
    try:
        service = _get_or_init_github_service(github_service, require_repo=False)
        if not _ensure_active_repository(service):
            return

        print(f"📂 Repositori de treball: {service.active_repo_name}")
        pr_num = _select_open_pull_request(service, "auditar")
        if pr_num is None:
            return

        reviewer = CodeReviewAgent(github_service=service, repo_name=service.active_repo_name)
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


def handle_remediation_option(github_service: Optional[GitHubService] = None) -> None:
    """Executa el flux interactiu de Remediació segons el Code Review al repositori actiu."""
    print("\n--- 🛠️ REMEDIACIÓ I REFACTORITZACIÓ SEGONS CODE REVIEW ---")
    try:
        service = _get_or_init_github_service(github_service, require_repo=False)
        if not _ensure_active_repository(service):
            return

        print(f"📂 Repositori de treball: {service.active_repo_name}")
        pr_num = _select_open_pull_request(service, "remediar")
        if pr_num is None:
            return

        developer = DeveloperAgent(github_service=service, repo_name=service.active_repo_name)
        resultat = developer.remediate_pull_request(pr_number=pr_num)

        if resultat["success"]:
            print(f"\n🎉 Remediació completada i pujada a la branca de la PR #{pr_num}!")
            print("💡 Ara pots tornar a executar l'Opció 4 per validar que la nova revisió sigui APROVADA.")
        else:
            print("\n⚠️ No s'ha pogut completar el procés de remediació autònoma.")
    except Exception as e:
        print(f"❌ Error durant el procés de remediació: {e}")


def _print_menu_header(active_repo: Optional[str]) -> None:
    """Mostra la capçalera del menú principal amb el nom del repositori actiu al principi.

    Args:
        active_repo: Nom del repositori seleccionat o None si encara no s'ha triat.
    """
    repo_label = active_repo if active_repo else "Cap repositori seleccionat"
    print("\n" + "=" * 60)
    print(f"📂 REPOSITORI ACTIU: {repo_label}")
    print("=" * 60)
    print("🤖 AGENT D'IA PER A DESENVOLUPAMENT AUTÒNOM DE PROGRAMARI")
    print("=" * 60)
    print("1. [Repositori] Seleccionar el repositori de GitHub sobre el qual treballar")
    print("2. [Analista] Crear una nova Issue a GitHub des d'un requeriment")
    print("3. [Desenvolupador] Desenvolupar i provar una Issue de GitHub")
    print("4. [Code Reviewer] Auditar una Pull Request (Nomenclatura + OWASP Top 10)")
    print("5. [Remediació] Refactoritzar i corregir una PR segons el Code Review")
    print("6. Sortir")


def main(github_service: Optional[GitHubService] = None) -> None:
    """Executa el bucle del menú principal interactiu amb suport multi-repositori.

    Args:
        github_service: Instància opcional de GitHubService (útil per a tests unitaris).
    """
    service: Optional[GitHubService] = github_service
    if service is None:
        try:
            service = GitHubService(repo_name=GITHUB_REPO, require_repo=False)
        except Exception as e:
            print(f"⚠️ Avís d'inicialització de GitHub: {e}")

    handlers: dict[str, Callable[[Optional[GitHubService]], Any]] = {
        "1": handle_repository_selection,
        "2": handle_analyst_option,
        "3": handle_developer_option,
        "4": handle_review_option,
        "5": handle_remediation_option,
    }

    while True:
        active_repo = service.active_repo_name if service is not None else None
        _print_menu_header(active_repo)

        try:
            opcio = input("\nSelecciona una opció (1/2/3/4/5/6): ").strip()
        except EOFError:
            print("\nFins aviat! 👋")
            break

        if opcio.lower() == "q" or opcio == "6":
            print("\nFins aviat! 👋")
            break

        handler = handlers.get(opcio)
        if handler is None:
            print("\n❌ Error: Opció no vàlida. Has de seleccionar 1, 2, 3, 4, 5 o 6.")
            continue

        handler(service)


if __name__ == "__main__":
    main()
