"""Paquet d'utilitats transversals: configuració, logging estructurat, parseig JSON i changelog."""

from src.utils.adr_manager import (
    adr_lock,
    build_adr_filename,
    get_next_adr_id,
    materialize_adr_file,
    slugify_title,
)
from src.utils.changelog_updater import (
    CHANGELOG_CATEGORIES,
    classify_commit_message,
    group_commits_by_category,
    release_unreleased_content,
    update_changelog_content,
    update_changelog_file,
)
from src.utils.config import GITHUB_REPOS, AppConfig, parse_repo_list
from src.utils.json_parser import (
    normalize_developer_files,
    parse_developer_json_response,
    parse_generic_json_response,
)
from src.utils.logger import AgentLogger, JSONFormatter, StructuredAgentAdapter

__all__ = [
    "AppConfig",
    "GITHUB_REPOS",
    "parse_repo_list",
    "CHANGELOG_CATEGORIES",
    "classify_commit_message",
    "group_commits_by_category",
    "release_unreleased_content",
    "update_changelog_content",
    "update_changelog_file",
    "AgentLogger",
    "JSONFormatter",
    "StructuredAgentAdapter",
    "normalize_developer_files",
    "parse_developer_json_response",
    "parse_generic_json_response",
    "slugify_title",
    "adr_lock",
    "get_next_adr_id",
    "build_adr_filename",
    "materialize_adr_file",
]
