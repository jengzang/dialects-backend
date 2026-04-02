"""Shared route-template normalization helpers for logging."""

from __future__ import annotations

from typing import Iterable


PATH_TEMPLATES: list[tuple[str, str]] = [
    ("/admin/sessions/user/", "{user_id}"),
    ("/admin/sessions/revoke-user/", "{user_id}"),
    ("/admin/sessions/revoke/", "{token_id}"),
    ("/admin/user-sessions/user/", "{user_id}"),
    ("/admin/user-sessions/revoke-user/", "{user_id}"),
    ("/admin/user-sessions/", "{session_id}"),
    ("/admin/ip/", "{api_name}/{ip}"),
    ("/api/tools/check/download/", "{task_id}"),
    ("/api/tools/jyut2ipa/download/", "{task_id}"),
    ("/api/tools/jyut2ipa/progress/", "{task_id}"),
    ("/api/tools/merge/download/", "{task_id}"),
    ("/api/tools/merge/progress/", "{task_id}"),
    ("/api/tools/praat/jobs/progress/", "{job_id}"),
    ("/api/tools/praat/uploads/progress/", "{task_id}"),
    ("/api/villages/admin/run-ids/active/", "{analysis_type}"),
    ("/api/villages/admin/run-ids/available/", "{analysis_type}"),
    ("/api/villages/admin/run-ids/metadata/", "{run_id}"),
    ("/api/villages/village/complete/", "{village_id}"),
    ("/api/villages/village/features/", "{village_id}"),
    ("/api/villages/village/ngrams/", "{village_id}"),
    ("/api/villages/village/semantic-structure/", "{village_id}"),
    ("/api/villages/village/spatial-features/", "{village_id}"),
    ("/api/villages/semantic/subcategory/chars/", "{subcategory}"),
    ("/api/villages/spatial/hotspots/", "{hotspot_id}"),
    ("/api/villages/spatial/integration/by-character/", "{character}"),
    ("/api/villages/spatial/integration/by-cluster/", "{cluster_id}"),
]


def _sorted_templates(
    templates: Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    return sorted(templates, key=lambda item: len(item[0]), reverse=True)


def normalize_route_path(path: str) -> str:
    """Normalize a concrete request path into a route template when possible."""
    for prefix, param_template in _sorted_templates(PATH_TEMPLATES):
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

