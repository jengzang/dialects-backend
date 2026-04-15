"""
tools 层共用配置。

这里集中放文件清理框架会用到的常量与 policy 注册表，避免继续把
“配置数据”和 “FileManager 实现细节” 混在同一个文件里。
"""

from __future__ import annotations

from typing import Any, Dict

CLEANUP_METADATA_VERSION = 1
GLOBAL_CLEANUP_FALLBACK_SECONDS = 12 * 60 * 60
CLEANUP_SCAN_INTERVAL_SECONDS = 5 * 60

TASK_CLEANUP_30M_SECONDS = 30 * 60
PRAAT_RESULT_READ_TTL_SECONDS = 5 * 60
CLUSTER_JOB_TTL_SECONDS = 2 * 60 * 60
CLUSTER_ARTIFACT_CAPACITY_BYTES = 1024 * 1024 * 1024

CLEANUP_POLICY_CHECK_WORKSPACE = "check_workspace"
CLEANUP_POLICY_MERGE_RESULT = "merge_result"
CLEANUP_POLICY_JYUT2IPA_RESULT = "jyut2ipa_result"
CLEANUP_POLICY_PRAAT_UPLOAD = "praat_upload"
CLEANUP_POLICY_CLUSTER_JOB = "cluster_job"
CLEANUP_POLICY_CLUSTER_PREVIEW = "cluster_preview"
CLEANUP_POLICY_CLUSTER_PREPARE = "cluster_prepare"
CLEANUP_POLICY_CLUSTER_DISTANCE = "cluster_distance"
CLEANUP_POLICY_CLUSTER_RESULT = "cluster_result"

DEFAULT_ARTIFACT_CAPACITY_LIMITS = {
    "cluster_artifacts": CLUSTER_ARTIFACT_CAPACITY_BYTES,
}

DEFAULT_CLEANUP_POLICIES: Dict[str, Dict[str, Any]] = {
    CLEANUP_POLICY_CHECK_WORKSPACE: {
        "object_type": "task",
        "tool_name": "check",
        "delete_mode": "task_dir",
    },
    CLEANUP_POLICY_MERGE_RESULT: {
        "object_type": "task",
        "tool_name": "merge",
        "delete_mode": "task_dir",
    },
    CLEANUP_POLICY_JYUT2IPA_RESULT: {
        "object_type": "task",
        "tool_name": "jyut2ipa",
        "delete_mode": "task_dir",
    },
    CLEANUP_POLICY_PRAAT_UPLOAD: {
        "object_type": "task",
        "tool_name": "praat",
        "delete_mode": "task_dir",
    },
    CLEANUP_POLICY_CLUSTER_JOB: {
        "object_type": "task",
        "tool_name": "cluster",
        "delete_mode": "task_dir",
    },
    CLEANUP_POLICY_CLUSTER_PREVIEW: {
        "object_type": "artifact",
        "tool_name": "cluster",
        "delete_mode": "manifest_files",
        "scan_glob": "_artifacts/preview/*.json",
        "capacity_group": "cluster_artifacts",
    },
    CLEANUP_POLICY_CLUSTER_PREPARE: {
        "object_type": "artifact",
        "tool_name": "cluster",
        "delete_mode": "manifest_files",
        "scan_glob": "_artifacts/prepare/*.json",
        "capacity_group": "cluster_artifacts",
    },
    CLEANUP_POLICY_CLUSTER_DISTANCE: {
        "object_type": "artifact",
        "tool_name": "cluster",
        "delete_mode": "manifest_files",
        "scan_glob": "_artifacts/distance/*.json",
        "capacity_group": "cluster_artifacts",
    },
    CLEANUP_POLICY_CLUSTER_RESULT: {
        "object_type": "artifact",
        "tool_name": "cluster",
        "delete_mode": "manifest_files",
        "scan_glob": "_artifacts/result/*.json",
        "capacity_group": "cluster_artifacts",
    },
}
