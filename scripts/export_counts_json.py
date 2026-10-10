#!/usr/bin/env python3
"""生成 syllable_counts / feature_counts / points 的静态导出 JSON（位图编码）。

位图：每个音节/特征值的 locations 从 id 数组编码成 base64 位串，
第 i 位 = 地点 id i 是否覆盖该音节。解码需配合 points（id→地点+经纬度）
和 locations_count（位宽）。id 空间两个 count 文件一致（同一 resolved 顺序），
共用同一份 points 映射文件。

用法：
    python scripts/export_counts_json.py                  # 今天日期, top1000
    python scripts/export_counts_json.py --top 500
    python scripts/export_counts_json.py --date 20260814 --out-dir export/
"""

import argparse
import base64
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.common.path import DIALECTS_DB_USER, QUERY_DB_USER
from app.sql.db_pool import get_db_pool
from app.service.core.feature_stats import (
    resolve_feature_locations,
    get_syllable_counts,
    get_feature_counts_for_request,
)

THRESHOLDS = {"聲母": 20, "韻母": 30, "聲調": 8}


def bitmap_from_ids(location_ids, n_locations):
    """地点 id 列表 -> base64 位图；第 i 位 = 地点 id i 是否覆盖。"""
    bits = bytearray(n_locations // 8 + (1 if n_locations % 8 else 0))
    for i in location_ids:
        bits[i // 8] |= 1 << (i % 8)
    return base64.b64encode(bytes(bits)).decode("ascii")


def ids_from_bitmap(bitmap, n_locations):
    """解码校验用：base64 位图 -> 地点 id 列表。"""
    data = base64.b64decode(bitmap)
    return [
        i
        for i in range(n_locations)
        if (data[i // 8] >> (i % 8)) & 1
    ]


def top_n(entries, n):
    ranked = sorted(entries.items(), key=lambda kv: (-kv[1]["totalCount"], kv[0]))
    return dict(ranked[:n])


def build_syllable_section(section, n_locations, top):
    return {
        syllable: {
            "totalCount": item["totalCount"],
            "locationCount": item["locationCount"],
            "bitmap": bitmap_from_ids(item["locations"], n_locations),
        }
        for syllable, item in top_n(section["aggregated"]["syllables"], top).items()
    }


def export_syllable_counts(result, top, out_dir, date):
    n_locations = len(result["points"])
    data = {
        "toneless": {
            "total_tokens": result["toneless"]["aggregated"]["total_tokens"],
            "unique_syllables": result["toneless"]["aggregated"]["unique_syllables"],
            "top": top,
            "syllables": build_syllable_section(result["toneless"], n_locations, top),
        },
        "toned": {
            "total_tokens": result["toned"]["aggregated"]["total_tokens"],
            "unique_syllables": result["toned"]["aggregated"]["unique_syllables"],
            "top": top,
            "syllables": build_syllable_section(result["toned"], n_locations, top),
        },
        "locations_count": n_locations,
        "meta": result["meta"],
    }
    path = os.path.join(out_dir, f"syllable_counts_{date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def export_feature_counts(aggregated, n_locations, out_dir, date):
    data = {"locations_count": n_locations}
    for feature, values in aggregated.items():
        threshold = THRESHOLDS[feature]
        data[feature] = {
            value: {
                "totalCount": item["totalCount"],
                "locationCount": item["locationCount"],
                "bitmap": bitmap_from_ids(item["locations"], n_locations),
            }
            for value, item in values.items()
            if item["totalCount"] >= threshold
        }
    path = os.path.join(out_dir, f"feature_counts_{date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def export_points(result, n_locations, out_dir, date):
    points = []
    for p in result["points"]:
        loc = p["location"]
        item = dict(p)
        item["unique_syllables"] = {
            "toneless": result["toneless"]["locations"].get(loc, {}).get("unique_syllables", 0),
            "toned": result["toned"]["locations"].get(loc, {}).get("unique_syllables", 0),
        }
        item["total_tokens"] = {
            "toneless": result["toneless"]["locations"].get(loc, {}).get("total_tokens", 0),
            "toned": result["toned"]["locations"].get(loc, {}).get("total_tokens", 0),
        }
        points.append(item)
    data = {
        "points": points,
        "locations_count": n_locations,
    }
    path = os.path.join(out_dir, f"points_{date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def main():
    parser = argparse.ArgumentParser(description="导出音节/特征统计 JSON（位图编码）")
    parser.add_argument("--top", type=int, default=1000, help="每档保留音节数（默认 1000）")
    parser.add_argument("--date", default=datetime.date.today().strftime("%Y%m%d"), help="输出文件名日期（默认今天）")
    parser.add_argument("--out-dir", default=".", help="输出目录（默认当前目录）")
    args = parser.parse_args()

    pool = get_db_pool(DIALECTS_DB_USER)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT 簡稱 FROM dialects")
        all_abbrs = [r[0] for r in cursor.fetchall()]
    resolved = resolve_feature_locations(all_abbrs, [], QUERY_DB_USER, region_mode="yindian")

    result = get_syllable_counts(resolved, DIALECTS_DB_USER, QUERY_DB_USER, normalize_onset=True)
    fc = get_feature_counts_for_request(all_abbrs, [], True, DIALECTS_DB_USER, QUERY_DB_USER)

    sc_order = [p["location"] for p in result["points"]]
    fc_order = list(fc["locations"].keys())
    if sc_order != fc_order:
        raise SystemExit("id 空间不一致：syllable_counts 与 feature_counts 的地点顺序不同")

    path_sc = export_syllable_counts(result, args.top, args.out_dir, args.date)
    path_fc = export_feature_counts(fc["aggregated"], len(sc_order), args.out_dir, args.date)
    path_pts = export_points(result, len(sc_order), args.out_dir, args.date)

    # 抽查解码一致性：写出的位图还原后应与原始 id 列表一致
    data = json.load(open(path_sc, encoding="utf-8"))
    first = next(iter(data["toneless"]["syllables"].items()))
    src = result["toneless"]["aggregated"]["syllables"][first[0]]["locations"]
    if ids_from_bitmap(first[1]["bitmap"], len(sc_order)) != src:
        raise SystemExit("位图解码校验失败")

    print(f"-> {path_sc}: {os.path.getsize(path_sc)/1e6:.2f} MB")
    print(f"-> {path_fc}: {os.path.getsize(path_fc)/1e6:.2f} MB")
    print(f"-> {path_pts}: {os.path.getsize(path_pts)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
