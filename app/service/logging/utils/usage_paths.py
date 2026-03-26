"""Path normalization helpers for auth.db usage tracking."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Iterable

from app.common.api_config import IGNORE_API, RECORD_API


AUTH_USAGE_RUNTIME_PATH_TEMPLATES: list[tuple[str, str]] = [
    # API - Villages (Admin)
    ("/api/villages/admin/run-ids/active/", "{analysis_type}"),
    ("/api/villages/admin/run-ids/available/", "{analysis_type}"),
    ("/api/villages/admin/run-ids/metadata/", "{run_id}"),
    # API - Villages (Village)
    ("/api/villages/village/complete/", "{village_id}"),
    ("/api/villages/village/features/", "{village_id}"),
    ("/api/villages/village/ngrams/", "{village_id}"),
    ("/api/villages/village/semantic-structure/", "{village_id}"),
    ("/api/villages/village/spatial-features/", "{village_id}"),
    # API - Villages (Semantic)
    ("/api/villages/semantic/subcategory/chars/", "{subcategory}"),
    # API - Villages (Spatial)
    ("/api/villages/spatial/hotspots/", "{hotspot_id}"),
    ("/api/villages/spatial/integration/by-character/", "{character}"),
    ("/api/villages/spatial/integration/by-cluster/", "{cluster_id}"),
]


AUTH_USAGE_MIGRATION_ONLY_TEMPLATES: list[tuple[str, str]] = [
    # Historical SQL metadata paths that may exist in legacy auth.db summary rows.
    ("/sql/distinct/", "{db_key}/{table_name}/{column}"),
    # Historical tool task paths that should no longer have been recorded in auth.db,
    # but may still exist in legacy summary rows.
    ("/api/tools/check/download/", "{task_id}"),
    ("/api/tools/jyut2ipa/download/", "{task_id}"),
    ("/api/tools/jyut2ipa/progress/", "{task_id}"),
    ("/api/tools/merge/download/", "{task_id}"),
    ("/api/tools/merge/progress/", "{task_id}"),
    ("/api/tools/praat/jobs/progress/", "{job_id}"),
    ("/api/tools/praat/uploads/progress/", "{task_id}"),
]


def _sorted_templates(
    templates: Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    return sorted(templates, key=lambda item: len(item[0]), reverse=True)


def _normalize_with_templates(path: str, templates: Iterable[tuple[str, str]]) -> str:
    for prefix, param_template in _sorted_templates(templates):
        if not path.startswith(prefix):
            continue

        suffix = path[len(prefix):]
        if not suffix:
            return path

        template_segments = param_template.split("/")
        suffix_segments = suffix.split("/")
        if len(suffix_segments) < len(template_segments):
            return path

        rest_segments = suffix_segments[len(template_segments):]
        if rest_segments:
            return f"{prefix}{param_template}/{'/'.join(rest_segments)}"

        return f"{prefix}{param_template}"

    return path


def normalize_auth_usage_path(path: str) -> str:
    """Normalize request paths before future auth.db usage writes."""
    return _normalize_with_templates(path, AUTH_USAGE_RUNTIME_PATH_TEMPLATES)


def normalize_auth_usage_path_for_migration(path: str) -> str:
    """Normalize runtime and legacy auth.db summary paths during one-off migration."""
    all_templates = AUTH_USAGE_RUNTIME_PATH_TEMPLATES + AUTH_USAGE_MIGRATION_ONLY_TEMPLATES
    return _normalize_with_templates(path, all_templates)


def auth_usage_path_needs_migration(path: str) -> bool:
    """Return True when an existing auth.db path would be normalized."""
    return normalize_auth_usage_path_for_migration(path) != path


def _path_matches_marker(path: str, marker: str) -> bool:
    if "*" in marker:
        return fnmatchcase(path, marker)
    return path == marker


def should_record_auth_usage(path: str) -> bool:
    """Return True when the request should be persisted into auth.db usage tables."""
    if any(_path_matches_marker(path, marker) for marker in IGNORE_API):
        return False
    return any(_path_matches_marker(path, marker) for marker in RECORD_API)
