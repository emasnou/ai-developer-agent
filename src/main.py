import sys
from pathlib import Path

# Afegir el directori arrel al sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.analyst_agent import AnalystAgent

def main():
    print("=" * 60)
    print("🤖 BENVINGUT A L'AGENT D'IA PER A DESENVOLUPAMENT DE PROGRAMARI")
    print("=" * 60)
    
    # 1. Demanar el títol i el requeriment a l'usuari interactivament
    issue_title = input("\n📌 Introdueix un títol breu per a la tasca (ex: feat: cercador de productes): ").strip()
    
    if not issue_title:
        print("❌ El títol no pot estar buit. Cancel·lant...")
        return

    print("\n📝 Descriu el requeriment o funcionalitat que vols crear:")
    print("(Escriu la teva descripció. Quan acabis, prem ENTER):\n")
    
    user_requirement = input("> ").strip()
    
    if not user_requirement:
        print("❌ El requeriment no pot estar buit. Cancel·lant...")
        return

    # 2. Processar la petició amb l'Agent Analista
    print("\n" + "-" * 60)
    analyst = AnalystAgent()
    
    resultat = analyst.process_requirement_and_create_issue(
        requirement=user_requirement,
        issue_title=issue_title
    )
    
    print("-" * 60)
    print(f"✅ Tasca generada per Gemini i publicada a GitHub!")
    print(f"🔗 Pots veure la Issue creada a: {resultat['url']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
