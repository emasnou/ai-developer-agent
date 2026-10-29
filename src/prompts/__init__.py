"""Paquet de plantilles de prompts de sistema i instruccions per als agents."""

from src.prompts.analyst_prompts import ANALYST_SYSTEM_PROMPT, build_analyst_system_prompt
from src.prompts.analytics_prompts import ANALYTICS_SYSTEM_PROMPT
from src.prompts.developer_prompts import (
    DEVELOPER_FIX_PROMPT,
    DEVELOPER_REMEDIATION_PROMPT,
    DEVELOPER_SYSTEM_PROMPT,
)
from src.prompts.review_prompts import (
    CODE_REVIEW_SYSTEM_PROMPT,
    EXTRACT_IMPROVEMENTS_PROMPT,
)

__all__ = [
    "ANALYST_SYSTEM_PROMPT",
    "ANALYTICS_SYSTEM_PROMPT",
    "build_analyst_system_prompt",
    "DEVELOPER_SYSTEM_PROMPT",
    "DEVELOPER_FIX_PROMPT",
    "DEVELOPER_REMEDIATION_PROMPT",
    "CODE_REVIEW_SYSTEM_PROMPT",
    "EXTRACT_IMPROVEMENTS_PROMPT",
]
