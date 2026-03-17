"""
子集分析API (Subset Analysis API)

提供自定义子集的聚类和对比分析：
- POST /api/compute/subset/cluster - 子集聚类
- POST /api/compute/subset/compare - 对比分析
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import logging
import time
import sqlite3
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from scipy.stats import chi2_contingency

from .validators import (
    SubsetClusteringParams,
    SubsetComparisonParams,
    SUBSET_SEMANTIC_TAG_WHITELIST,
)
from .cache import compute_cache
from .timeout import timeout, TimeoutException
from ..config import get_db_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compute/subset")

SUBSET_SEMANTIC_COLUMNS = [f"sem_{tag}" for tag in sorted(SUBSET_SEMANTIC_TAG_WHITELIST)]
SUBSET_BASE_COLUMNS = ["village_id", "village_name", "city", "county", "name_length", "suffix_1"]
SUBSET_SELECTABLE_COLUMNS = set(SUBSET_BASE_COLUMNS + SUBSET_SEMANTIC_COLUMNS)


def _build_select_clause(select_columns: Optional[List[str]]) -> str:
    if not select_columns:
        return "*"

    selected = []
    invalid = []
    seen = set()
    for col in select_columns:
        if col in seen:
            continue
        seen.add(col)
        if col in SUBSET_SELECTABLE_COLUMNS:
            selected.append(col)
        else:
            invalid.append(col)

    if invalid:
        raise HTTPException(status_code=422, detail=f"Invalid select columns: {invalid}")

    if not selected:
        selected = ["village_id"]

    return ", ".join(selected)


def _build_compare_required_columns(analysis: Dict[str, Any]) -> List[str]:
    required = {"village_id"}

    if analysis.get("semantic_distribution", True):
        required.update(SUBSET_SEMANTIC_COLUMNS)

    if analysis.get("morphology_patterns", True):
        required.update({"name_length", "suffix_1"})

    if analysis.get("character_distribution", False):
        required.add("village_name")

    if analysis.get("spatial_distribution", False):
        required.add("village_id")

    return sorted(required)


def filter_villages(
    conn: sqlite3.Connection,
    filter_params: Dict[str, Any],
    select_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    根据过滤条件筛选村庄

    Args:
        conn: 数据库连接
        filter_params: 过滤参数

    Returns:
        过滤后的DataFrame
    """
    select_clause = _build_select_clause(select_columns)
    query = f"SELECT {select_clause} FROM village_features WHERE 1=1"
    params = []

    # 城市过滤
    if filter_params.get('cities'):
        placeholders = ','.join(['?' for _ in filter_params['cities']])
        query += f" AND city IN ({placeholders})"
        params.extend(filter_params['cities'])

    # 县区过滤
    if filter_params.get('counties'):
        placeholders = ','.join(['?' for _ in filter_params['counties']])
        query += f" AND county IN ({placeholders})"
        params.extend(filter_params['counties'])

    # 语义标签过滤（白名单，防止列名注入）
    if filter_params.get('semantic_tags'):
        for tag in filter_params['semantic_tags']:
            if tag not in SUBSET_SEMANTIC_TAG_WHITELIST:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid semantic tag: {tag}"
                )
            query += f" AND sem_{tag} = 1"

    # 名称模糊匹配
    if filter_params.get('name_pattern'):
        query += " AND village_name LIKE ?"
        params.append(f"%{filter_params['name_pattern']}%")

    df = pd.read_sql_query(query, conn, params=params)

    # 采样
    sample_size = filter_params.get('sample_size')
    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)

    return df


def get_villages_by_ids(
    conn: sqlite3.Connection,
    village_ids: List[int],
    select_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    根据村庄ID列表获取村庄数据

    Args:
        conn: 数据库连接
        village_ids: 村庄ID列表

    Returns:
        村庄数据DataFrame
    """
    # 标准化 ID 格式（添加 v_ 前缀）
    normalized_ids = []
    for vid in village_ids:
        vid_str = str(vid)
        if not vid_str.startswith('v_'):
            vid_str = f'v_{vid_str}'
        normalized_ids.append(vid_str)

    # 去重可减少 SQL 占位符和扫描成本；IN 查询本身也不会返回重复行
    normalized_ids = list(dict.fromkeys(normalized_ids))
    if not normalized_ids:
        return pd.DataFrame()

    # 批量查询（分批处理以避免 SQL 表达式树过大）
    select_clause = _build_select_clause(select_columns)
    batch_size = 500
    all_dfs = []

    for i in range(0, len(normalized_ids), batch_size):
        batch_ids = normalized_ids[i:i + batch_size]
        placeholders = ','.join(['?' for _ in batch_ids])
        query = f"SELECT {select_clause} FROM village_features WHERE village_id IN ({placeholders})"
        df_batch = pd.read_sql_query(query, conn, params=batch_ids)
        all_dfs.append(df_batch)

    # 合并所有批次
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()


@router.post("/cluster")
async def cluster_subset(
    params: SubsetClusteringParams
) -> Dict[str, Any]:
    """
    对自定义子集进行聚类（需要登录）

    Args:
        params: 子集聚类参数
    Returns:
        聚类结果

    Raises:
        HTTPException: 如果聚类失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("subset_cluster", params.dict())
        if cached_result:
            logger.info("Returning cached subset clustering result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Clustering subset with filter: {params.filter.dict()}")

        # 执行子集聚类（带超时控制）
        with timeout(5):  # 5秒超时
            start_time = time.time()

            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            clustering_features = params.clustering.get('features', [])
            select_columns = ["village_id", "village_name"]
            if 'semantic' in clustering_features:
                select_columns.extend(SUBSET_SEMANTIC_COLUMNS)
            if 'morphology' in clustering_features:
                select_columns.append('name_length')
            if 'semantic' not in clustering_features and 'morphology' not in clustering_features:
                conn.close()
                raise HTTPException(
                    status_code=422,
                    detail="No clustering features selected. Choose at least one of: semantic, morphology."
                )

            # 1. 过滤村庄
            df = filter_villages(conn, params.filter.dict(), select_columns=select_columns)
            matched_count = len(df)

            if matched_count == 0:
                conn.close()
                return {
                    'subset_id': f"subset_{int(time.time())}",
                    'matched_villages': 0,
                    'sampled_villages': 0,
                    'execution_time_ms': 0,
                    'clusters': [],
                    'metrics': {},
                    'from_cache': False
                }

            # 2. 构建特征矩阵
            feature_cols = []
            if 'semantic' in clustering_features:
                feature_cols.extend([col for col in SUBSET_SEMANTIC_COLUMNS if col in df.columns])

            if 'morphology' in clustering_features:
                feature_cols.append('name_length')

            if not feature_cols:
                conn.close()
                raise HTTPException(
                    status_code=422,
                    detail="No clustering features selected. Choose at least one of: semantic, morphology."
                )

            X = df[feature_cols].values
            X = np.nan_to_num(X, nan=0.0)

            # 3. 标准化
            X = StandardScaler().fit_transform(X)

            # 4. 聚类
            algorithm = params.clustering.get('algorithm', 'kmeans')
            k = params.clustering.get('k', 3)

            if algorithm == 'kmeans':
                model = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = model.fit_predict(X)
            elif algorithm == 'dbscan':
                model = DBSCAN(eps=0.5, min_samples=5)
                labels = model.fit_predict(X)
            else:
                labels = np.zeros(len(X), dtype=int)

            # 5. 评估
            metrics = {}
            if len(set(labels)) > 1:
                metrics['silhouette_score'] = float(silhouette_score(X, labels))

            # 6. 聚类结果
            clusters = []
            for cluster_id in sorted(set(labels)):
                if cluster_id == -1:
                    continue
                mask = labels == cluster_id
                cluster_villages = df[mask]['village_name'].tolist()[:10]
                clusters.append({
                    'cluster_id': int(cluster_id),
                    'size': int(mask.sum()),
                    'sample_villages': cluster_villages
                })

            conn.close()

            execution_time = int((time.time() - start_time) * 1000)

            result = {
                'subset_id': f"subset_{int(time.time())}",
                'matched_villages': matched_count,
                'sampled_villages': len(df),
                'execution_time_ms': execution_time,
                'clusters': clusters,
                'metrics': metrics
            }

        # 缓存结果
        compute_cache.set("subset_cluster", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Subset clustering timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Subset clustering validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Subset clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


@router.post("/compare")
async def compare_subsets(
    params: SubsetComparisonParams
) -> Dict[str, Any]:
    """
    对比两个子集（需要登录）

    Args:
        params: 对比参数
    Returns:
        对比结果

    Raises:
        HTTPException: 如果对比失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("subset_compare", params.dict())
        if cached_result:
            logger.info("Returning cached comparison result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Comparing subsets: {params.group_a.label} vs {params.group_b.label}")

        # 执行对比分析（带超时控制）
        with timeout(5):  # 5秒超时
            start_time = time.time()
            timings = {}  # 性能监控

            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 1. 获取两组村庄数据（支持 village_ids 或 filter 两种模式）
            t0 = time.time()
            required_columns = _build_compare_required_columns(params.analysis)
            if params.group_a.village_ids is not None:
                df_a = get_villages_by_ids(conn, params.group_a.village_ids, select_columns=required_columns)
            else:
                df_a = filter_villages(conn, params.group_a.filter.dict(), select_columns=required_columns)

            if params.group_b.village_ids is not None:
                df_b = get_villages_by_ids(conn, params.group_b.village_ids, select_columns=required_columns)
            else:
                df_b = filter_villages(conn, params.group_b.filter.dict(), select_columns=required_columns)
            timings['data_loading'] = int((time.time() - t0) * 1000)

            group_a_size = len(df_a)
            group_b_size = len(df_b)

            semantic_comparison = []
            morphology_comparison = []
            character_comparison = []
            spatial_comparison = []
            significant_differences = []

            # 2. 语义分布对比
            t0 = time.time()
            if params.analysis.get('semantic_distribution', True):
                semantic_cols = [col for col in df_a.columns if col.startswith('sem_')]

                for col in semantic_cols:
                    count_a = df_a[col].sum()
                    count_b = df_b[col].sum()
                    pct_a = count_a / group_a_size if group_a_size > 0 else 0
                    pct_b = count_b / group_b_size if group_b_size > 0 else 0

                    semantic_comparison.append({
                        'category': col.replace('sem_', ''),
                        'group_a_count': int(count_a),
                        'group_a_pct': float(pct_a),
                        'group_b_count': int(count_b),
                        'group_b_pct': float(pct_b),
                        'difference': float(pct_a - pct_b)
                    })

                # 卡方检验
                if params.analysis.get('statistical_test') == 'chi_square':
                    for col in semantic_cols:
                        contingency_table = [
                            [df_a[col].sum(), group_a_size - df_a[col].sum()],
                            [df_b[col].sum(), group_b_size - df_b[col].sum()]
                        ]
                        try:
                            chi2, p_value, _, _ = chi2_contingency(contingency_table)
                            if p_value < 0.05:
                                significant_differences.append({
                                    'feature': col.replace('sem_', ''),
                                    'test': 'chi_square',
                                    'statistic': float(chi2),
                                    'p_value': float(p_value)
                                })
                        except Exception as e:
                            logger.warning(f"Chi-square test failed for {col}: {e}")

            if params.analysis.get('semantic_distribution', True):
                timings['semantic'] = int((time.time() - t0) * 1000)

            # 3. 形态学对比（扩展）
            t0 = time.time()
            if params.analysis.get('morphology_patterns', True):
                # 平均名称长度
                avg_len_a = df_a['name_length'].mean() if 'name_length' in df_a.columns else 0
                avg_len_b = df_b['name_length'].mean() if 'name_length' in df_b.columns else 0

                morphology_comparison.append({
                    'feature': 'avg_name_length',
                    'group_a_value': float(avg_len_a),
                    'group_b_value': float(avg_len_b),
                    'difference': float(avg_len_a - avg_len_b)
                })

                # 名称长度分布
                if 'name_length' in df_a.columns and 'name_length' in df_b.columns:
                    len_dist_a = df_a['name_length'].value_counts(normalize=True).to_dict()
                    len_dist_b = df_b['name_length'].value_counts(normalize=True).to_dict()

                    # 对比每个长度的占比
                    all_lengths = sorted(set(len_dist_a.keys()) | set(len_dist_b.keys()))
                    for length in all_lengths:
                        pct_a = len_dist_a.get(length, 0)
                        pct_b = len_dist_b.get(length, 0)
                        morphology_comparison.append({
                            'feature': f'length_{length}_pct',
                            'group_a_value': float(pct_a),
                            'group_b_value': float(pct_b),
                            'difference': float(pct_a - pct_b)
                        })

                # 前缀对比（Top 10）
                if 'suffix_1' in df_a.columns and 'suffix_1' in df_b.columns:
                    suffix_a = df_a['suffix_1'].value_counts(normalize=True).head(10).to_dict()
                    suffix_b = df_b['suffix_1'].value_counts(normalize=True).head(10).to_dict()

                    all_suffixes = sorted(set(suffix_a.keys()) | set(suffix_b.keys()))
                    for suffix in all_suffixes:
                        if suffix and suffix != '':  # 跳过空值
                            pct_a = suffix_a.get(suffix, 0)
                            pct_b = suffix_b.get(suffix, 0)
                            morphology_comparison.append({
                                'feature': f'suffix_{suffix}',
                                'group_a_value': float(pct_a),
                                'group_b_value': float(pct_b),
                                'difference': float(pct_a - pct_b)
                            })

            if params.analysis.get('morphology_patterns', True):
                timings['morphology'] = int((time.time() - t0) * 1000)

            # 4. 字符特征对比（优化版）
            t0 = time.time()
            if params.analysis.get('character_distribution', False):
                if 'village_name' in df_a.columns and 'village_name' in df_b.columns:
                    from collections import Counter

                    # 优化：使用 join 一次性处理所有字符
                    all_names_a = ''.join(df_a['village_name'].dropna().astype(str))
                    all_names_b = ''.join(df_b['village_name'].dropna().astype(str))

                    chars_a = Counter(all_names_a)
                    chars_b = Counter(all_names_b)

                    # 计算频率（Top 20）
                    total_chars_a = sum(chars_a.values())
                    total_chars_b = sum(chars_b.values())

                    top_chars_a = (
                        {char: count / total_chars_a for char, count in chars_a.most_common(20)}
                        if total_chars_a > 0 else {}
                    )
                    top_chars_b = (
                        {char: count / total_chars_b for char, count in chars_b.most_common(20)}
                        if total_chars_b > 0 else {}
                    )

                    # 对比高频字符
                    all_chars = sorted(set(top_chars_a.keys()) | set(top_chars_b.keys()))
                    for char in all_chars:
                        freq_a = top_chars_a.get(char, 0)
                        freq_b = top_chars_b.get(char, 0)
                        character_comparison.append({
                            'char': char,
                            'group_a_freq': float(freq_a),
                            'group_b_freq': float(freq_b),
                            'difference': float(freq_a - freq_b),
                            'lift': float(freq_a / freq_b) if freq_b > 0 else None
                        })

                    # 按差异排序
                    character_comparison.sort(key=lambda x: abs(x['difference']), reverse=True)

            if params.analysis.get('character_distribution', False):
                timings['character'] = int((time.time() - t0) * 1000)

            # 5. 空间特征对比（优化版）
            t0 = time.time()
            if params.analysis.get('spatial_distribution', False):
                if group_a_size > 0 and group_b_size > 0:
                    # 获取村庄ID列表
                    village_ids_a = df_a['village_id'].tolist()
                    village_ids_b = df_b['village_id'].tolist()

                    # 优化：合并查询，一次性获取两组数据
                    def get_spatial_stats_batch(village_ids_list):
                        """批量获取多组村庄的空间统计"""
                        all_village_ids = []
                        seen_ids = set()
                        for ids in village_ids_list:
                            for vid in ids:
                                if vid in seen_ids:
                                    continue
                                seen_ids.add(vid)
                                all_village_ids.append(vid)

                        # 一次性查询所有坐标
                        batch_size = 1000  # 增大批次
                        all_coords = {}
                        for i in range(0, len(all_village_ids), batch_size):
                            batch = all_village_ids[i:i + batch_size]
                            placeholders = ','.join(['?' for _ in batch])
                            query = f"""
                            SELECT village_id, longitude, latitude
                            FROM 广东省自然村_预处理
                            WHERE village_id IN ({placeholders})
                            AND longitude IS NOT NULL AND latitude IS NOT NULL
                            """
                            cursor.execute(query, batch)
                            for row in cursor.fetchall():
                                all_coords[row[0]] = (row[1], row[2])

                        # 分组统计
                        results = []
                        for ids in village_ids_list:
                            coords = [all_coords[vid] for vid in ids if vid in all_coords]
                            if coords:
                                lons = [c[0] for c in coords]
                                lats = [c[1] for c in coords]
                                results.append({
                                    'count': len(coords),
                                    'lon_min': min(lons),
                                    'lon_max': max(lons),
                                    'lon_mean': sum(lons) / len(lons),
                                    'lat_min': min(lats),
                                    'lat_max': max(lats),
                                    'lat_mean': sum(lats) / len(lats),
                                    'lon_range': max(lons) - min(lons),
                                    'lat_range': max(lats) - min(lats)
                                })
                            else:
                                results.append(None)
                        return results

                    stats_list = get_spatial_stats_batch([village_ids_a, village_ids_b])
                    stats_a, stats_b = stats_list[0], stats_list[1]

                    if stats_a and stats_b:
                        spatial_comparison = {
                            'group_a': stats_a,
                            'group_b': stats_b,
                            'centroid_distance_km': float(
                                ((stats_a['lon_mean'] - stats_b['lon_mean'])**2 +
                                 (stats_a['lat_mean'] - stats_b['lat_mean'])**2)**0.5 * 111
                            )
                        }

            if params.analysis.get('spatial_distribution', False):
                timings['spatial'] = int((time.time() - t0) * 1000)

            conn.close()

            execution_time = int((time.time() - start_time) * 1000)

            result = {
                'comparison_id': f"compare_{int(time.time())}",
                'group_a_size': group_a_size,
                'group_b_size': group_b_size,
                'execution_time_ms': execution_time,
                'timings': timings,  # 性能监控
                'semantic_comparison': semantic_comparison,
                'morphology_comparison': morphology_comparison,
                'character_comparison': character_comparison,
                'spatial_comparison': spatial_comparison,
                'significant_differences': significant_differences
            }

        # 缓存结果
        compute_cache.set("subset_compare", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Subset comparison timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Subset comparison validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Subset comparison error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")

