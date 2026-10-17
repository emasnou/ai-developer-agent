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

## 🚀 Configuració i Instal·lació

### 1. Requisits Previs
* **Python**: Versió 3.10 o superior.
* **GitHub**: Un repositori (privat o públic).
* **GitHub Token**: Un *Personal Access Token (PAT)* amb permisos de `repo`.
* **API Key de Gemini**: Una clau d'API de Google Gemini.

### 2. Instal·lació de Dependències
Clona el repositori i instal·la els paquets necessaris utilitzant `pip`:

```bash
pip install -r requirements.txt

>### 3. Configuració de Variables d'Entorn
Crea un fitxer `.env` a l'arrel del projecte utilitzant la plantilla `.env.example`:

```bash
cp .env.example .env
```

Edita el fitxer `.env` i afegeix-hi les teves credencials i claus d'API:

```env
GITHUB_TOKEN=ghp_el_teu_github_token_aqui
GITHUB_REPO=el-teu-usuari/nom-del-repositori
GEMINI_API_KEY=la_teva_clau_api_de_gemini
```

---

## 💻 Ús

Per executar l'agent en mode interactiu des de la línia de comandes:

```bash
python3 -m src.main
```

L'agent et demanarà:
1. Un **títol** per a la tasca.
2. La **descripció o requeriment** en text pla de la funcionalitat que vols desenvolupar.

L'**Agent Analista** processarà la petició mitjançant Gemini i publicarà immediatament una nova Issue a GitHub estructurada amb:
* 📝 **Història d'Usuari** (*Com a... Vull... Per a...*)
* 🎯 **Criteris d'Acceptació** (*Given-When-Then*)
* 🧪 **Matriu de Proves de Qualitat** (*Tests unitaris i d'integració*)

