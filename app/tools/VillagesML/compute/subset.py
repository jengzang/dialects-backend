"""
子集分析API (Subset Analysis API)

提供自定义子集的聚类和对比分析：
- POST /api/compute/subset/cluster - 子集聚类
- POST /api/compute/subset/compare - 对比分析
"""

from fastapi import APIRouter, HTTPException, Depends
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

from .validators import SubsetClusteringParams, SubsetComparisonParams
from .cache import compute_cache
from .timeout import timeout, TimeoutException
from ..config import get_db_path

# 导入身份验证依赖
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compute/subset")


def filter_villages(conn: sqlite3.Connection, filter_params: Dict[str, Any]) -> pd.DataFrame:
    """
    根据过滤条件筛选村庄

    Args:
        conn: 数据库连接
        filter_params: 过滤参数

    Returns:
        过滤后的DataFrame
    """
    query = "SELECT * FROM village_features WHERE 1=1"
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

    # 语义标签过滤
    if filter_params.get('semantic_tags'):
        for tag in filter_params['semantic_tags']:
            query += f" AND sem_{tag} = 1"

    df = pd.read_sql_query(query, conn, params=params)

    # 采样
    sample_size = filter_params.get('sample_size')
    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)

    return df


@router.post("/cluster")
async def cluster_subset(
    params: SubsetClusteringParams,
    user: Optional[User] = Depends(ApiLimiter)  # 添加身份验证
) -> Dict[str, Any]:
    """
    对自定义子集进行聚类（需要登录）

    Args:
        params: 子集聚类参数
        user: 当前用户（由 ApiLimiter 自动验证）

    Returns:
        聚类结果

    Raises:
        HTTPException: 如果未登录、聚类失败或超时
    """
    # 检查用户是否登录
    if not user:
        raise HTTPException(status_code=401, detail="此功能需要登录")

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

            # 1. 过滤村庄
            df = filter_villages(conn, params.filter.dict())
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
            if 'semantic' in params.clustering.features:
                semantic_cols = [col for col in df.columns if col.startswith('sem_')]
                feature_cols.extend(semantic_cols)

            if 'morphology' in params.clustering.features:
                feature_cols.append('name_length')

            X = df[feature_cols].values
            X = np.nan_to_num(X, nan=0.0)

            # 3. 标准化
            X = StandardScaler().fit_transform(X)

            # 4. 聚类
            algorithm = params.clustering.algorithm
            k = params.clustering.k

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

    except Exception as e:
        logger.error(f"Subset clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


@router.post("/compare")
async def compare_subsets(
    params: SubsetComparisonParams,
    user: Optional[User] = Depends(ApiLimiter)  # 添加身份验证
) -> Dict[str, Any]:
    """
    对比两个子集（需要登录）

    Args:
        params: 对比参数
        user: 当前用户（由 ApiLimiter 自动验证）

    Returns:
        对比结果

    Raises:
        HTTPException: 如果未登录、对比失败或超时
    """
    # 检查用户是否登录
    if not user:
        raise HTTPException(status_code=401, detail="此功能需要登录")

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

            db_path = get_db_path()
            conn = sqlite3.connect(db_path)

            # 1. 过滤两组村庄
            df_a = filter_villages(conn, params.group_a.filter.dict())
            df_b = filter_villages(conn, params.group_b.filter.dict())

            group_a_size = len(df_a)
            group_b_size = len(df_b)

            semantic_comparison = []
            morphology_comparison = []
            significant_differences = []

            # 2. 语义分布对比
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

            # 3. 形态学对比
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

            conn.close()

            execution_time = int((time.time() - start_time) * 1000)

            result = {
                'comparison_id': f"compare_{int(time.time())}",
                'group_a_size': group_a_size,
                'group_b_size': group_b_size,
                'execution_time_ms': execution_time,
                'semantic_comparison': semantic_comparison,
                'morphology_comparison': morphology_comparison,
                'significant_differences': significant_differences
            }

        # 缓存结果
        compute_cache.set("subset_compare", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Subset comparison timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except Exception as e:
        logger.error(f"Subset comparison error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")

