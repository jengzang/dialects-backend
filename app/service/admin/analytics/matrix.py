from typing import Optional
from sqlalchemy.orm import Session
from app.service.auth.database import models


def get_user_api_matrix(
    db: Session,
    min_calls: int = 1,
    exclude_paths: Optional[str] = None,
    max_users: int = 500,
    max_paths: int = 100,
):
    exclude_list = []
    if exclude_paths:
        exclude_list = [p.strip() for p in exclude_paths.split(",") if p.strip()]

    query = db.query(
        models.ApiUsageSummary.user_id,
        models.ApiUsageSummary.path,
        models.ApiUsageSummary.count,
        models.ApiUsageSummary.total_upload,
        models.ApiUsageSummary.total_download,
        models.ApiUsageSummary.total_duration,
    ).filter(
        models.ApiUsageSummary.user_id.isnot(None),
        models.ApiUsageSummary.count >= min_calls,
    )

    for p in exclude_list:
        if p.endswith("*"):
            query = query.filter(~models.ApiUsageSummary.path.like(p[:-1] + "%"))
        else:
            query = query.filter(models.ApiUsageSummary.path != p)

    rows = query.all()

    user_agg = {}
    path_agg = {}

    for row in rows:
        uid, path, count, upload, download, duration = row

        if uid not in user_agg:
            user_agg[uid] = {"total_calls": 0, "unique_apis": set()}
        user_agg[uid]["total_calls"] += count
        user_agg[uid]["unique_apis"].add(path)

        if path not in path_agg:
            path_agg[path] = {"total_calls": 0, "unique_users": set()}
        path_agg[path]["total_calls"] += count
        path_agg[path]["unique_users"].add(uid)

    top_users = sorted(user_agg.items(), key=lambda x: x[1]["total_calls"], reverse=True)[:max_users]

    top_paths = sorted(path_agg.items(), key=lambda x: x[1]["total_calls"], reverse=True)[:max_paths]

    user_index_map = {}
    users = []
    for uid, agg in top_users:
        user_index_map[uid] = len(users)
        users.append({
            "user_id": uid,
            "username": "",
            "total_calls": agg["total_calls"],
            "unique_apis": len(agg["unique_apis"]),
        })

    path_index_map = {}
    paths = []
    for p, agg in top_paths:
        path_index_map[p] = len(paths)
        paths.append({
            "path": p,
            "total_calls": agg["total_calls"],
            "unique_users": len(agg["unique_users"]),
        })

    matrix = []
    for row in rows:
        uid, path, count, upload, download, duration = row
        if uid not in user_index_map or path not in path_index_map:
            continue
        matrix.append({
            "user_index": user_index_map[uid],
            "path_index": path_index_map[path],
            "count": count,
            "total_upload": float(upload or 0),
            "total_download": float(download or 0),
            "total_duration": float(duration or 0),
        })

    user_ids_for_names = [u["user_id"] for u in users]
    user_map = {}
    if user_ids_for_names:
        db_users = db.query(models.User.id, models.User.username).filter(
            models.User.id.in_(user_ids_for_names)
        ).all()
        user_map = {u.id: u.username for u in db_users}

    for u in users:
        u["username"] = user_map.get(u["user_id"], f"user_{u['user_id']}")

    total_users = len(user_agg)
    total_paths = len(path_agg)

    return {
        "meta": {
            "min_calls": min_calls,
            "max_users": max_users,
            "max_paths": max_paths,
            "exclude_paths": exclude_paths,
            "returned_users": len(users),
            "returned_paths": len(paths),
            "returned_cells": len(matrix),
            "users_truncated": total_users > max_users,
            "paths_truncated": total_paths > max_paths,
        },
        "users": users,
        "paths": paths,
        "matrix": matrix,
    }
