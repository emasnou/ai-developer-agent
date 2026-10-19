import sys
from pathlib import Path

# Afegir el directori arrel al sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.analyst_agent import AnalystAgent
from src.agents.developer_agent import DeveloperAgent
from src.agents.code_review_agent import CodeReviewAgent
from src.services.github_service import GitHubService

def main():
    print("=" * 60)
    print("🤖 AGENT D'IA PER A DESENVOLUPAMENT AUTÒNOM DE PROGRAMARI")
    print("=" * 60)
    print("1. [Analista] Crear una nova Issue a GitHub des d'un requeriment")
    print("2. [Desenvolupador] Desenvolupar i provar una Issue de GitHub")
    print("3. [Code Reviewer] Auditar una Pull Request (Nomenclatura + OWASP Top 10)")
    print("4. [Remediació] Refactoritzar i corregir una PR segons el Code Review")
    print("5. Sortir")

    # 1. Validació de l'opció del menú principal    
    opcio = input("\nSelecciona una opció (1/2/3/4/5): ").strip()
    
    if opcio not in ["1", "2", "3","4","5"]:
        print("\n❌ Error: Opció no vàlida. Has de seleccionar 1, 2 o 3.")
        return

    if opcio == "5" or opcio.lower() == 'q':
        print("\nFins aviat! 👋")
        return

    if opcio == "1":
        print("\n--- 📝 NOU REQUERIMENT PER A L'AGENT ANALISTA ---")
        
        # Validació del títol
        issue_title = input("📌 Títol de la tasca: ").strip()
        while not issue_title:
            print("⚠️ El títol no pot estar buit.")
            issue_title = input("📌 Títol de la tasca: ").strip()
            
        # Validació de la descripció del requeriment
        print("\n📝 Descriu el requeriment o funcionalitat que vols crear:")
        user_requirement = input("> ").strip()
        while not user_requirement:
            print("⚠️ El requeriment no pot estar buit.")
            user_requirement = input("> ").strip()
        
        try:
            analyst = AnalystAgent()
            resultat = analyst.process_requirement_and_create_issue(user_requirement, issue_title)
            print(f"\n✅ Issue creada amb èxit a: {resultat['url']}")
        except Exception as e:
            print(f"\n❌ Error durant el procés de creació de la Issue: {e}")

    elif opcio == "2":
        print("\n--- 🛠️ DESENVOLUPAMENT DE TASQUES AMB L'AGENT DESENVOLUPADOR ---")
        
        try:
            github_service = GitHubService()
            open_issues = github_service.get_open_issues()
            
            if not open_issues:
                print("ℹ️ No hi ha cap Issue oberta pendent de desenvolupament al repositori.")
                return

            print("\n📋 Llista de les Issues obertes a GitHub:\n")
            issues_dict = {}
            for issue in open_issues:
                issues_dict[issue.number] = issue
                print(f"  [#{issue.number}] - {issue.title}")

            # Entrada i selecció validada de la Issue
            selected_issue_number = None
            while selected_issue_number is None:
                user_input = input("\n📌 Introdueix el número (ID) de la Issue que vols desenvolupar (o 'q' per eixir): ").strip()
                
                if user_input.lower() == 'q':
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

            # Execució de l'Agent Desenvolupador sobre la Issue seleccionada
            developer = DeveloperAgent()
            resultat = developer.develop_and_test(issue_number=selected_issue_number)
            
            if resultat["success"]:
                print(f"\n🎉 Desenvolupament completat amb èxit en {resultat['attempts']} intent(s)!")
            else:
                print("\n⚠️ No s'ha pogut completar el desenvolupament de manera autònoma.")

        except Exception as e:
            print(f"\n❌ S'ha produït un error en recuperar o processar la tasca: {e}")

    elif opcio == "3":
        print("\n--- 🔍 AUDITORIA DE CODI I SEGURETAT (CODE REVIEW) ---")
        try:
            github_service = GitHubService()
            prs = github_service.get_pull_requests()
            
            if not prs:
                print("ℹ️ No hi ha cap Pull Request oberta pendent de revisió.")
                return

            print("\n📋 Pull Requests obertes a GitHub:\n")
            pr_dict = {}
            for pr in prs:
                pr_dict[pr.number] = pr
                print(f"  [#{pr.number}] - {pr.title} (Branca: {pr.head.ref})")

            user_input = input("\n📌 Introdueix el número de la PR a auditar (o 'q' per eixir): ").strip()
            if user_input.lower() == 'q' or not user_input.isdigit():
                return
                
            pr_num = int(user_input)
            if pr_num not in pr_dict:
                print(f"⚠️ La PR #{pr_num} no existeix a la llista.")
                return
            # Fem la revisió de la pull request.
            reviewer = CodeReviewAgent()
            resultat = reviewer.review_pull_request(pr_number=pr_num)
            
            print("\n" + "=" * 60)
            print(resultat["report"])
            print("=" * 60)
            # Si la PR està APROVADA, extreure les recomanacions de futur com a Issues de millora (enhancement)
            if resultat["approved"]:
                print("\n🎉 La Pull Request ha estat APROVADA!")
                created_issues = reviewer.create_future_improvement_issues(
                    pr_number=pr_num,
                    review_report=resultat["report"]
                )
                if created_issues:
                    print(f"\n✅ S'han creat {len(created_issues)} Issue(s) de millora futura amb l'etiqueta 'enhancement':")
                    for iss in created_issues:
                        print(f"  - [{iss['title']}] ({iss['url']})")
                else:
                    print("ℹ️ No s'han trobat millores addicionals a registrar.")

        except Exception as e:
            print(f"❌ Error durant el procés de Code Review: {e}")
    elif opcio == "4":
        print("\n--- 🛠️ REMEDIACIÓ I REFACTORITZACIÓ SEGONS CODE REVIEW ---")
        try:
            github_service = GitHubService()
            prs = github_service.get_pull_requests()
            
            if not prs:
                print("ℹ️ No hi ha cap Pull Request oberta per a remediar.")
                return

            print("\n📋 Pull Requests obertes a GitHub:\n")
            pr_dict = {}
            for pr in prs:
                pr_dict[pr.number] = pr
                print(f"  [#{pr.number}] - {pr.title} (Branca: {pr.head.ref})")

            user_input = input("\n📌 Introdueix el número de la PR a remediar (o 'q' per eixir): ").strip()
            if user_input.lower() == 'q' or not user_input.isdigit():
                return
                
            pr_num = int(user_input)
            if pr_num not in pr_dict:
                print(f"⚠️ La PR #{pr_num} no existeix a la llista.")
                return

            developer = DeveloperAgent()
            resultat = developer.remediate_pull_request(pr_number=pr_num)
            
            if resultat["success"]:
                print(f"\n🎉 Remediació completada i pujada a la branca de la PR #{pr_num}!")
                print("💡 Ara pots tornar a executar l'Opció 3 per validar que la nova revisió sigui APROVADA.")
            else:
                print("\n⚠️ No s'ha pogut completar el procés de remediació autònoma.")

        except Exception as e:
            print(f"❌ Error durant el procés de remediació: {e}")


if __name__ == "__main__":
    main()
