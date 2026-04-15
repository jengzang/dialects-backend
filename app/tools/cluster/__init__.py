"""
cluster 工具的对外导出入口。

外部调用方如果只关心“生成 snapshot / 执行聚类 / 查询结果”，
可以直接从这里拿到稳定入口，而不用了解内部 service 的拆分方式。
"""

from .service.cluster_service import (
    build_cluster_distance_state,
    build_cluster_final_result,
    build_cluster_prepare_state,
    build_cluster_result,
    build_task_summary,
    get_cluster_result,
    get_task_status_payload,
    resolve_cluster_groups,
    resolve_cluster_job_snapshot,
    run_cluster_job,
)

__all__ = [
    "build_cluster_distance_state",
    "build_cluster_final_result",
    "build_cluster_prepare_state",
    "build_cluster_result",
    "build_task_summary",
    "get_cluster_result",
    "get_task_status_payload",
    "resolve_cluster_groups",
    "resolve_cluster_job_snapshot",
    "run_cluster_job",
]
