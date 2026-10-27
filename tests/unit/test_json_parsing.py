"""Tests unitaris per al parser resilient de respostes JSON/YAML i aïllament de l'entorn del workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.agents.code_review_agent import CodeReviewAgent
from src.agents.developer_agent import DeveloperAgent


def test_developer_agent_parse_clean_json() -> None:
    """Verifica el parseig directe d'un JSON ben formatat retornat per l'agent desenvolupador."""
    agent = DeveloperAgent()
    raw = (
        '{"summary": "Test summary", '
        '"files": [{"path": "src/test.py", "action": "create", "content": "print(1)"}]}'
    )
    result = agent._parse_json_response(raw)
    assert result["summary"] == "Test summary"
    assert len(result["files"]) == 1
    assert result["files"][0]["path"] == "src/test.py"


def test_developer_agent_parse_with_markdown_fences() -> None:
    """Verifica l'extracció i neteja de blocs Markdown (```json ... ```) en la resposta del LLM."""
    agent = DeveloperAgent()
    raw = """```json
{
  "summary": "Fenced summary",
  "files": [
    {
      "path": "src/fenced.py",
      "action": "modify",
      "content": "def foo():\\n    return 42"
    }
  ]
}
```"""
    result = agent._parse_json_response(raw)
    assert result["summary"] == "Fenced summary"
    assert len(result["files"]) == 1
    assert result["files"][0]["path"] == "src/fenced.py"


def test_developer_agent_parse_triple_quotes_content() -> None:
    """Verifica que el cas crític de gemini-3.5-flash-lite amb ''' en 'content' es resolgui correctament."""
    agent = DeveloperAgent()
    raw = """{
  "summary": "Triple quote issue",
  "files": [
    {
      "path": "src/ops.py",
      "action": "create_or_modify",
      "content": '''
import os
import sys

def run():
    print('hello world')
'''
    }
  ]
}"""
    result = agent._parse_json_response(raw)
    assert result["summary"] == "Triple quote issue"
    assert len(result["files"]) == 1
    assert "import os" in result["files"][0]["content"]


def test_developer_agent_parse_single_quotes_and_escapes() -> None:
    """Verifica que expressions regulars amb barres o cometes simples no trenquin el parseig."""
    agent = DeveloperAgent()
    raw = r"""{
  'summary': 'Regex escapes',
  'files': [
    {
      'path': 'src/regex.py',
      'action': 'create',
      'content': "import re\npattern = re.compile(r'\\d+\\s*')\n"
    }
  ]
}"""
    result = agent._parse_json_response(raw)
    assert len(result["files"]) == 1
    assert result["files"][0]["path"] == "src/regex.py"


def test_developer_agent_parse_list_from_repair() -> None:
    """Verifica el cas on repair_json retorna una llista d'objectes en lloc d'un diccionari arrel."""
    agent = DeveloperAgent()
    raw = (
        '[{"summary": "From list", '
        '"files": [{"path": "a.py", "action": "create", "content": "x = 1"}]}]'
    )
    result = agent._parse_json_response(raw)
    assert result["summary"] == "From list"
    assert len(result["files"]) == 1


def test_code_review_agent_parse_json() -> None:
    """Verifica que CodeReviewAgent parseja una resposta JSON d'auditoria amb camps approved i report."""
    agent = CodeReviewAgent()
    raw = '{"approved": true, "report": "## Aprovat\\nTot correcte."}'
    result = agent._parse_json_response(raw)
    assert result["approved"] is True
    assert "Aprovat" in result["report"]


def test_base_agent_lazy_services_and_dependency_injection() -> None:
    """Verifica que instanciar un agent no crea connexions externes fins que s'accedeix als serveis."""
    mock_llm: Any = MagicMock()
    mock_gh: Any = MagicMock()
    agent = DeveloperAgent(llm_service=mock_llm, github_service=mock_gh)
    assert agent.llm is mock_llm
    assert agent.github is mock_gh


def test_developer_agent_workspace_env_strips_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que _build_workspace_env filtra les claus d'API sensibles i aïlla el PYTHONPATH.

    Args:
        tmp_path: Directori temporal proporcionat per PyTest per simular el workspace.
        monkeypatch: Fixture de PyTest per modificar variables d'entorn de forma aïllada.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "secret_gh_token")
    monkeypatch.setenv("GEMINI_API_KEY", "secret_gemini_key")
    monkeypatch.setenv("PYTHONPATH", "/host/contaminated/path")
    monkeypatch.setenv("SAFE_VAR", "safe_value")

    env = DeveloperAgent._build_workspace_env(tmp_path)
    assert "GITHUB_TOKEN" not in env
    assert "GEMINI_API_KEY" not in env
    assert env.get("SAFE_VAR") == "safe_value"
    assert "/host/contaminated/path" not in env.get("PYTHONPATH", "")
    assert str(tmp_path.resolve()) in env.get("PYTHONPATH", "")
    assert str((tmp_path / "src").resolve()) in env.get("PYTHONPATH", "")
