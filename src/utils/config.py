import os
from dotenv import load_dotenv

# Carrega les variables del fitxer .env
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
#OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GITHUB_TOKEN or not GITHUB_REPO:
    raise ValueError("Falten les variables GITHUB_TOKEN o GITHUB_REPO al fitxer .env")
if not GEMINI_API_KEY:
    raise ValueError("Falta la variable GEMINI_API_KEY al fitxer .env")

