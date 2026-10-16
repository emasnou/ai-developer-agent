# 🤖 AI Developer Agent

Un agent autònom basat en IA dissenyat per automatitzar el cicle de vida del desenvolupament de programari: des de l'anàlisi de requisits i la creació de tasques amb la seva matriu de qualitat (QA), fins a la generació de codi, l'execució de tests automatitzats i la publicació a GitHub.

---

## 📐 Arquitectura del Sistema

El projecte s'organitza en 4 capes principals:

1. **Cervell / Model LLM:** Utilitza l'API oficial de **Google Gemini** (`google-genai`) per al raonament i la generació d'especificacions estructurades.
2. **Orquestrador de Tasques:** Integració directa amb l'API de **GitHub Issues** per a la creació automatitzada de requeriments, criteris d'acceptació (BDD) i matriu de proves de QA.
3. **Agent Desenvolupador & Entorn d'Execució:** Generació de codi Python i tests unitaris (`pytest`) en un entorn d'execució segur.
4. **Resiliència:** Sistema de reintents automàtics amb retard expositiu (`tenacity`) per gestionar pics de caràcter temporal o alta demanda a l'API del LLM.

---

## 📁 Estructura del Projecte

```text
ai-developer-agent/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── src/
│   ├── agents/
│   │   ├── analyst_agent.py      # Agent Analista (Product Owner)
│   │   └── developer_agent.py    # Agent Desenvolupador (Coder & Tester)
│   ├── services/
│   │   ├── github_service.py     # Integració amb l'API de GitHub
│   │   └── llm_service.py        # Client de Gemini amb reintents automàtics
│   ├── prompts/
│   │   └── analyst_prompts.py    # Plantilles de prompt per a l'anàlisi
│   ├── utils/
│   │   └── config.py             # Configuració i carrega de variables d'entorn
│   └── main.py                   # Interfície CLI principal
├── tests/
│   ├── unit/
│   └── integration/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt# ai-developer-agent
