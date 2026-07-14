"""
计算引擎模块 (Compute Engine)

提供核心计算功能：
- ClusteringEngine: 聚类分析
- SemanticEngine: 语义分析
- FeatureEngine: 特征提取
"""

import time
from contextlib import contextmanager
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score,
    calinski_harabasz_score
)
import logging
from app.sql.db_pool import get_db_pool
from ..schema_config import DEFAULT_DATABASE_KEY
from ..schema_keys import C, REGION_LEVEL_CONFIGS, T, TABLE_VARIANTS, semantic_feature_column
from ..schema_runtime import (
    qcolumn,
    qtable,
    normalize_region_level,
    region_level_config,
    run_id_analysis_type,
    table_variant,
)
from .validators import SUBSET_SEMANTIC_TAG_WHITELIST

_SEM_NAMES = sorted(SUBSET_SEMANTIC_TAG_WHITELIST)

logger = logging.getLogger(__name__)


class ClusteringEngine:
    """聚类计算引擎"""

    def __init__(self, db_path: str, dbpath: str = DEFAULT_DATABASE_KEY):
        """
        初始化聚类引擎

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.dbpath = dbpath
        self._db_pool = get_db_pool(db_path)
        self.feature_cache = {}  # 特征矩阵缓存

    @contextmanager
    def _connection(self):
        with self._db_pool.get_connection() as conn:
            yield conn

    def _table(self, logical_table: str) -> str:
        return qtable(self.dbpath, logical_table)

    def _column(self, logical_table: str, logical_column: str) -> str:
        return qcolumn(self.dbpath, logical_table, logical_column)

    def get_regional_features(
        self,
        region_level: str,
        feature_config: Dict[str, Any],
        region_filter: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[str]]:
        """
        获取区域特征矩阵。

        优先从预计算的聚合表读取；聚合表为空时回退到 village_features 实时聚合。
        """
        cache_key = f"{region_level}:{hash(str(feature_config))}:{hash(str(region_filter))}"

        if cache_key in self.feature_cache:
            logger.info(f"Using cached features for {region_level}")
            return self.feature_cache[cache_key]

        cfg = region_level_config(self.dbpath, REGION_LEVEL_CONFIGS.COMPUTE_AGGREGATE_FEATURES, region_level)
        region_col = cfg['region_col']
        filter_col = cfg['filter_col']
        applied_filter = False  # track whether region_filter was already applied in SQL

        agg_df = None
        with self._connection() as conn:
            agg_table = self._table(cfg['agg_table'])
            try:
                agg_df = pd.read_sql_query(f"SELECT * FROM {agg_table}", conn)
            except Exception as e:
                logger.info(f"Aggregate table {agg_table} unavailable: {e}")

        if agg_df is None or len(agg_df) == 0:
            logger.info(f"Aggregate table {agg_table} missing/empty, computing from village_features")
            with self._connection() as conn:
                vf_table = self._table(T.VILLAGE_FEATURES)
                sem_names = _SEM_NAMES
                sem_cols = [self._column(T.VILLAGE_FEATURES, semantic_feature_column(n)) for n in sem_names]
                sem_pct_exprs = [
                    f"SUM({c}) * 100.0 / NULLIF(COUNT(*), 0) AS sem_{n}_pct"
                    for c, n in zip(sem_cols, sem_names)
                ]
                group_cols = [self._column(T.VILLAGE_FEATURES, g) for g in cfg['group_cols']]
                select_parts = group_cols + [
                    "COUNT(*) AS total_villages",
                    f"AVG({self._column(T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.NAME_LENGTH)}) AS avg_name_length",
                ] + sem_pct_exprs
                query = f"SELECT {', '.join(select_parts)} FROM {vf_table}"
                params = None
                if region_filter:
                    filter_col_physical = self._column(T.VILLAGE_FEATURES, filter_col)
                    placeholders = ','.join(['?' for _ in region_filter])
                    query += f" WHERE {filter_col_physical} IN ({placeholders})"
                    params = region_filter
                query += f" GROUP BY {', '.join(group_cols)}"
                df_regional = pd.read_sql_query(query, conn, params=params)
                for g in cfg['group_cols']:
                    physical = self._column(T.VILLAGE_FEATURES, g).strip('"')
                    if physical in df_regional.columns and physical != g:
                        df_regional[g] = df_regional[physical]
                applied_filter = True
        else:
            df_regional = agg_df

        # region_filter for aggregate-table path (not yet filtered)
        if region_filter and not applied_filter and len(df_regional) > 0:
            if filter_col in df_regional.columns:
                df_regional = df_regional[df_regional[filter_col].isin(region_filter)]

        region_names = df_regional[region_col].tolist()

        # 构建特征向量
        feature_columns = []

        if feature_config.get('use_semantic', True):
            semantic_cols = [f'sem_{n}_pct' for n in _SEM_NAMES]
            feature_columns.extend([col for col in semantic_cols if col in df_regional.columns])

        if feature_config.get('use_morphology', True):
            feature_columns.append('avg_name_length')

        if feature_config.get('use_diversity', True):
            feature_columns.append('total_villages')

        # 提取特征矩阵
        X = df_regional[feature_columns].values
        X = np.nan_to_num(X, nan=0.0)

        if X.shape[0] == 0:
            raise ValueError(
                f"No regional data available for region_level='{region_level}'."
                f" Both aggregate table and village_features returned empty."
            )

        self.feature_cache[cache_key] = (X, region_names)
        logger.info(f"Built feature matrix: {X.shape} for {len(region_names)} regions")

        return X, region_names

    def run_clustering(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行聚类分析

        Args:
            params: 聚类参数

        Returns:
            聚类结果字典
        """
        start_time = time.time()

        # 1. 获取特征矩阵
        X, region_names = self.get_regional_features(
            params['region_level'],
            params['features'],
            params.get('region_filter')
        )

        # 2. 预处理
        if params['preprocessing']['standardize']:
            X = StandardScaler().fit_transform(X)
            logger.info("Features standardized")

        if params['preprocessing']['use_pca']:
            n_components = min(params['preprocessing']['pca_n_components'], X.shape[1])
            pca = PCA(n_components=n_components)
            X = pca.fit_transform(X)
            logger.info(f"PCA applied: {X.shape[1]} components")

        # 3. 聚类
        algorithm = params['algorithm']
        labels = None
        distances = None

        if algorithm == 'kmeans':
            model = KMeans(
                n_clusters=params['k'],
                random_state=params['random_state'],
                n_init=10,
                max_iter=300
            )
            labels = model.fit_predict(X)
            distances = model.transform(X).min(axis=1)
            logger.info(f"KMeans clustering completed: k={params['k']}")

        elif algorithm == 'dbscan':
            # 使用配置的参数或默认值
            dbscan_config = params.get('dbscan_config', {})
            eps = dbscan_config.get('eps', 0.5)
            min_samples = dbscan_config.get('min_samples', 5)

            # 对于小数据集,自动调整参数
            n_samples = X.shape[0]
            if n_samples < 30 and eps == 0.5 and min_samples == 5:
                # 自动调整为更宽松的参数
                eps = 1.5
                min_samples = max(2, n_samples // 10)
                logger.info(f"Auto-adjusted DBSCAN params for small dataset: eps={eps}, min_samples={min_samples}")

            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(X)
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise = list(labels).count(-1)
            logger.info(f"DBSCAN clustering completed: {n_clusters} clusters, {n_noise} noise points")

        elif algorithm == 'gmm':
            model = GaussianMixture(
                n_components=params['k'],
                random_state=params['random_state']
            )
            labels = model.fit_predict(X)
            logger.info(f"GMM clustering completed: k={params['k']}")

        # 4. 评估指标
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = list(labels).count(-1)

        metrics = {}
        if len(set(labels)) > 1:  # 至少2个聚类
            metrics['silhouette_score'] = float(silhouette_score(X, labels))
            metrics['davies_bouldin_index'] = float(davies_bouldin_score(X, labels))
            metrics['calinski_harabasz_score'] = float(calinski_harabasz_score(X, labels))
        else:
            metrics['silhouette_score'] = 0.0
            metrics['davies_bouldin_index'] = 0.0
            metrics['calinski_harabasz_score'] = 0.0

        # 添加聚类统计
        metrics['n_clusters'] = n_clusters
        metrics['n_noise'] = n_noise
        metrics['noise_ratio'] = round(n_noise / len(labels), 3) if len(labels) > 0 else 0.0

        # 5. 聚类分配
        assignments = []
        for i in range(len(region_names)):
            assignment = {
                'region_name': region_names[i],
                'cluster_id': int(labels[i])
            }
            if distances is not None:
                assignment['distance'] = float(distances[i])
            assignments.append(assignment)

        # 6. 聚类画像
        cluster_profiles = self._generate_cluster_profiles(X, labels, region_names)

        execution_time = int((time.time() - start_time) * 1000)

        # 生成参数建议(仅DBSCAN)
        param_suggestion = None
        if algorithm == 'dbscan':
            param_suggestion = self._suggest_dbscan_params(n_clusters, n_noise, len(region_names))

        result = {
            'run_id': f"online_clustering_{int(time.time())}",
            'algorithm': algorithm,
            'k': params.get('k'),
            'n_regions': len(region_names),
            'execution_time_ms': execution_time,
            'metrics': metrics,
            'assignments': assignments,
            'cluster_profiles': cluster_profiles
        }

        if param_suggestion:
            result['param_suggestion'] = param_suggestion

        return result

    def _generate_cluster_profiles(
        self,
        X: np.ndarray,
        labels: np.ndarray,
        region_names: List[str]
    ) -> List[Dict[str, Any]]:
        """
        生成聚类画像

        Args:
            X: 特征矩阵
            labels: 聚类标签
            region_names: 区域名称

        Returns:
            聚类画像列表
        """
        profiles = []
        unique_labels = sorted(set(labels))

        for cluster_id in unique_labels:
            if cluster_id == -1:  # DBSCAN噪声点
                continue

            mask = labels == cluster_id
            cluster_regions = [region_names[i] for i in range(len(region_names)) if mask[i]]
            cluster_features = X[mask]

            # 计算聚类中心
            centroid = cluster_features.mean(axis=0)

            # 特征重要性（简化版，使用方差）
            feature_importance = cluster_features.std(axis=0)

            profile = {
                'cluster_id': int(cluster_id),
                'region_count': int(mask.sum()),
                'regions': cluster_regions[:10],  # 只返回前10个
                'centroid_norm': float(np.linalg.norm(centroid)),
                'intra_cluster_variance': float(cluster_features.var())
            }
            profiles.append(profile)

        return profiles

    def _suggest_dbscan_params(
        self,
        n_clusters: int,
        n_noise: int,
        n_samples: int
    ) -> Dict[str, Any]:
        """
        根据聚类结果建议DBSCAN参数调整

        Args:
            n_clusters: 聚类数量
            n_noise: 噪声点数量
            n_samples: 样本总数

        Returns:
            参数建议字典
        """
        noise_ratio = n_noise / n_samples if n_samples > 0 else 0

        if n_clusters == 0:
            # 全是噪声点 - 参数太严格
            return {
                'status': 'too_strict',
                'message': '所有点都是噪声,参数过于严格',
                'suggestion': '增大eps(如+0.3)或减小min_samples(如-1)',
                'recommended_action': 'increase_eps'
            }
        elif n_clusters == 1 and n_noise == 0:
            # 只有一个聚类 - 参数太宽松
            return {
                'status': 'too_loose',
                'message': '所有点在同一聚类,参数过于宽松',
                'suggestion': '减小eps(如-0.3)或增大min_samples(如+1)',
                'recommended_action': 'decrease_eps'
            }
        elif noise_ratio > 0.3:
            # 噪声点过多
            return {
                'status': 'high_noise',
                'message': f'噪声点比例过高({noise_ratio:.1%})',
                'suggestion': '适当增大eps或减小min_samples',
                'recommended_action': 'increase_eps'
            }
        elif n_clusters > n_samples * 0.5:
            # 聚类过于碎片化
            return {
                'status': 'too_fragmented',
                'message': f'聚类过于碎片化({n_clusters}个聚类)',
                'suggestion': '增大eps以合并小聚类',
                'recommended_action': 'increase_eps'
            }
        else:
            # 参数合理
            return {
                'status': 'good',
                'message': f'聚类效果良好({n_clusters}个聚类,{noise_ratio:.1%}噪声)',
                'suggestion': '参数设置合理',
                'recommended_action': 'none'
            }

    def _build_character_tendency_features(
        self,
        region_level: str,
        top_n_chars: int,
        tendency_metric: str,
        region_filter: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[str], List[str]]:
        """
        构建字符倾向性特征矩阵

        Args:
            region_level: 区域级别
            top_n_chars: 每个区域选择top N字符
            tendency_metric: 倾向性指标 (z_score/lift/log_odds)
            region_filter: 区域过滤器

        Returns:
            (特征矩阵, 区域名称列表, 字符列表)
        """
        # 枚举对象转字符串（Pydantic .dict() 保留枚举对象，f-string 会输出 "TendencyMetric.Z_SCORE"）
        if hasattr(tendency_metric, 'value'):
            tendency_metric = tendency_metric.value
        if hasattr(region_level, 'value'):
            region_level = region_level.value

        # 映射region_level到数据库中的region_level值
        db_level_map = {
            'city': 'city',
            'county': 'county',
            'township': 'township'
        }
        db_level = db_level_map.get(region_level, 'county')

        # region_filter 语义：传入的是"父级区域名"，用于限制目标级别的范围
        # - city 级：用户传城市名 → 过滤 region_name（region_name 本身就是城市名）
        # - county 级：用户传城市名 → 过滤 city 列（取该市下所有县）
        # - township 级：用户传县名 → 过滤 county 列（取该县下所有镇）
        filter_col_map = {
            'city': self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME),
            'county': self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CITY),
            'township': self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.COUNTY),
        }
        filter_col = filter_col_map.get(db_level, self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME))

        region_filter_clause = ""
        params = []
        if region_filter:
            placeholders = ','.join(['?' for _ in region_filter])
            region_filter_clause = f" AND {filter_col} IN ({placeholders})"
            params = list(region_filter)

        query = f"""
        SELECT region, char, {tendency_metric}
        FROM (
            SELECT region, char, {tendency_metric},
                   ROW_NUMBER() OVER (PARTITION BY region ORDER BY {tendency_metric} DESC) as rn
            FROM (
                SELECT {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} as region, {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CHAR)} as char, MAX({tendency_metric}) as {tendency_metric}
                FROM {self._table(T.CHAR_REGIONAL_ANALYSIS)}
                WHERE {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)} = ?{region_filter_clause}
                GROUP BY {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)}, {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CHAR)}
            )
        )
        WHERE rn <= ?
        """
        params = [normalize_region_level(self.dbpath, T.CHAR_REGIONAL_ANALYSIS, db_level)] + params + [top_n_chars]

        with self._connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        # Pivot操作：region × character矩阵
        pivot_df = df.pivot(index='region', columns='char', values=tendency_metric)

        # 缺失值填充为0
        pivot_df = pivot_df.fillna(0)

        region_names = pivot_df.index.tolist()
        characters = pivot_df.columns.tolist()
        X = pivot_df.values

        logger.info(f"Built character tendency matrix: {X.shape} ({len(region_names)} regions × {len(characters)} chars)")

        return X, region_names, characters

    def _sample_villages(
        self,
        df: pd.DataFrame,
        strategy: str,
        sample_size: int,
        random_state: int
    ) -> pd.DataFrame:
        """
        村庄采样

        Args:
            df: 村庄数据框
            strategy: 采样策略 (random/stratified/spatial)
            sample_size: 采样大小
            random_state: 随机种子

        Returns:
            采样后的数据框
        """
        if len(df) <= sample_size:
            return df

        if strategy == "random":
            return df.sample(n=sample_size, random_state=random_state)

        elif strategy == "stratified":
            # 按县分层采样，保持区域分布
            if 'county' not in df.columns:
                logger.warning("County column not found, falling back to random sampling")
                return df.sample(n=sample_size, random_state=random_state)

            county_counts = df['county'].value_counts()
            total = len(df)

            # 计算每个县应采样的数量
            samples_per_county = (county_counts / total * sample_size).astype(int)

            # 确保至少采样1个
            samples_per_county = samples_per_county.clip(lower=1)

            # 调整总数
            if samples_per_county.sum() > sample_size:
                # 从最大的县减少
                diff = samples_per_county.sum() - sample_size
                largest_counties = samples_per_county.nlargest(diff).index
                for county in largest_counties:
                    samples_per_county[county] -= 1

            sampled_dfs = []
            for county, n_samples in samples_per_county.items():
                county_df = df[df['county'] == county]
                if len(county_df) >= n_samples:
                    sampled_dfs.append(county_df.sample(n=n_samples, random_state=random_state))
                else:
                    sampled_dfs.append(county_df)

            return pd.concat(sampled_dfs, ignore_index=True)

        elif strategy == "spatial":
            # 空间网格采样，确保地理均匀性
            if 'longitude' not in df.columns or 'latitude' not in df.columns:
                logger.warning("Spatial columns not found, falling back to random sampling")
                return df.sample(n=sample_size, random_state=random_state)

            # 将坐标空间划分为50×50网格
            n_grids = 50
            df['grid_x'] = pd.cut(df['longitude'], bins=n_grids, labels=False)
            df['grid_y'] = pd.cut(df['latitude'], bins=n_grids, labels=False)
            df['grid_id'] = df['grid_x'].astype(str) + '_' + df['grid_y'].astype(str)

            # 计算每个网格应采样的数量
            grid_counts = df['grid_id'].value_counts()
            samples_per_grid = max(1, sample_size // len(grid_counts))

            sampled_dfs = []
            for grid_id in grid_counts.index:
                grid_df = df[df['grid_id'] == grid_id]
                n_samples = min(samples_per_grid, len(grid_df))
                sampled_dfs.append(grid_df.sample(n=n_samples, random_state=random_state))

            result = pd.concat(sampled_dfs, ignore_index=True)

            # 如果采样不足，随机补充
            if len(result) < sample_size:
                remaining = df[~df.index.isin(result.index)]
                additional = remaining.sample(n=sample_size - len(result), random_state=random_state)
                result = pd.concat([result, additional], ignore_index=True)

            # 删除临时列
            result = result.drop(columns=['grid_x', 'grid_y', 'grid_id'])

            return result.head(sample_size)

        else:
            raise ValueError(f"Unknown sampling strategy: {strategy}")

    def _fetch_village_rows_by_rowids(
        self,
        conn,
        rowids: List[int],
        chunk_size: int = 800
    ) -> pd.DataFrame:
        """
        按 rowid 批量回表查询 village_features，避免 ORDER BY RANDOM() 全表排序。
        """
        if not rowids:
            return pd.DataFrame()

        # 去重并保持顺序
        ordered_ids: List[int] = []
        seen = set()
        for row_id in rowids:
            row_id_int = int(row_id)
            if row_id_int not in seen:
                seen.add(row_id_int)
                ordered_ids.append(row_id_int)

        frames = []
        for i in range(0, len(ordered_ids), chunk_size):
            batch = ordered_ids[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(batch))
            query = f"SELECT * FROM {self._table(T.VILLAGE_FEATURES)} WHERE rowid IN ({placeholders})"
            frames.append(pd.read_sql_query(query, conn, params=batch))

        if not frames:
            return pd.DataFrame()

        return pd.concat(frames, ignore_index=True)

    def _parse_spatial_json(
        self,
        run_id: str
    ) -> Tuple[np.ndarray, List[int], Dict[str, Any]]:
        """
        解析空间聚类JSON字段

        Args:
            run_id: 空间聚类运行ID

        Returns:
            (特征矩阵, 聚类ID列表, 元数据)
        """
        query = """
        SELECT
            cluster_id,
            cluster_size,
            semantic_profile_json,
            naming_patterns_json,
            centroid_lon,
            centroid_lat
        FROM {table}
        WHERE {run_id_col} = ?
        """
        query = query.format(
            table=self._table(T.SPATIAL_CLUSTERS),
            run_id_col=self._column(T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.RUN_ID),
        )

        with self._connection() as conn:
            df = pd.read_sql_query(query, conn, params=[run_id])

        if len(df) == 0:
            raise ValueError(f"No spatial clusters found for run_id: {run_id}")

        logger.info(f"Loaded {len(df)} spatial clusters for run_id: {run_id}")

        # 对>5000聚类自动采样到5000
        if len(df) > 5000:
            logger.info(f"Sampling {len(df)} clusters down to 5000")
            df = df.sample(n=5000, random_state=42)

        cluster_ids = df['cluster_id'].tolist()

        # 解析JSON字段并构建特征向量
        import json

        features_list = []

        for _, row in df.iterrows():
            feature_vec = []

            # 语义特征
            try:
                semantic_profile = json.loads(row['semantic_profile_json']) if pd.notna(row['semantic_profile_json']) else {}
                # 提取9个主要语义类别的百分比
                for category in _SEM_NAMES:
                    feature_vec.append(semantic_profile.get(f'{category}_pct', 0.0))
            except:
                feature_vec.extend([0.0] * len(_SEM_NAMES))

            # 命名模式特征
            try:
                naming_patterns = json.loads(row['naming_patterns_json']) if pd.notna(row['naming_patterns_json']) else {}
                # 提取top 3后缀/前缀的频率
                top_suffixes = naming_patterns.get('top_suffixes', [])
                for i in range(3):
                    if i < len(top_suffixes):
                        feature_vec.append(top_suffixes[i].get('frequency', 0))
                    else:
                        feature_vec.append(0)
            except:
                feature_vec.extend([0.0] * 3)

            # 地理特征
            feature_vec.append(row['centroid_lon'] if pd.notna(row['centroid_lon']) else 0.0)
            feature_vec.append(row['centroid_lat'] if pd.notna(row['centroid_lat']) else 0.0)

            # 聚类大小
            feature_vec.append(row['cluster_size'] if pd.notna(row['cluster_size']) else 0)

            features_list.append(feature_vec)

        X = np.array(features_list)

        metadata = {
            'original_count': len(df),
            'run_id': run_id
        }

        logger.info(f"Built spatial feature matrix: {X.shape}")

        return X, cluster_ids, metadata

    def run_character_tendency_clustering(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行字符倾向性聚类

        Args:
            params: 聚类参数

        Returns:
            聚类结果字典
        """
        start_time = time.time()

        # 1. 构建字符倾向性特征矩阵
        X, region_names, characters = self._build_character_tendency_features(
            params['region_level'],
            params['top_n_chars'],
            params['tendency_metric'],
            params.get('region_filter')
        )

        # 2. 预处理
        if params['preprocessing']['standardize']:
            X = StandardScaler().fit_transform(X)
            logger.info("Features standardized")

        if params['preprocessing']['use_pca']:
            n_components = min(params['preprocessing']['pca_n_components'], X.shape[1])
            pca = PCA(n_components=n_components)
            X = pca.fit_transform(X)
            logger.info(f"PCA applied: {X.shape[1]} components")

        # 3. 聚类
        algorithm = params['algorithm']
        # 枚举对象转字符串（Pydantic .dict() 保留枚举对象）
        if hasattr(algorithm, 'value'):
            algorithm = algorithm.value
        labels = None

        if algorithm == 'kmeans':
            model = KMeans(
                n_clusters=params['k'],
                random_state=params['random_state'],
                n_init=10,
                max_iter=300
            )
            labels = model.fit_predict(X)
            logger.info(f"KMeans clustering completed: k={params['k']}")

        elif algorithm == 'dbscan':
            dbscan_cfg = params.get('dbscan_config') or {}
            eps = dbscan_cfg.get('eps', 0.5) if isinstance(dbscan_cfg, dict) else getattr(dbscan_cfg, 'eps', 0.5)
            min_samples = dbscan_cfg.get('min_samples', 5) if isinstance(dbscan_cfg, dict) else getattr(dbscan_cfg, 'min_samples', 5)
            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(X)
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            logger.info(f"DBSCAN clustering completed: {n_clusters} clusters")

        elif algorithm == 'gmm':
            model = GaussianMixture(
                n_components=params['k'],
                random_state=params['random_state']
            )
            labels = model.fit_predict(X)
            logger.info(f"GMM clustering completed: k={params['k']}")

        # 4. 评估指标
        metrics = {}
        if len(set(labels)) > 1:
            metrics['silhouette_score'] = float(silhouette_score(X, labels))
            metrics['davies_bouldin_index'] = float(davies_bouldin_score(X, labels))
            metrics['calinski_harabasz_score'] = float(calinski_harabasz_score(X, labels))
        else:
            metrics['silhouette_score'] = 0.0
            metrics['davies_bouldin_index'] = 0.0
            metrics['calinski_harabasz_score'] = 0.0

        # 5. 聚类分配
        assignments = []
        for i in range(len(region_names)):
            assignments.append({
                'region_name': region_names[i],
                'cluster_id': int(labels[i])
            })

        # 6. 聚类画像
        cluster_profiles = self._generate_cluster_profiles(X, labels, region_names)

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'run_id': f"char_tendency_{int(time.time())}",
            'algorithm': algorithm,
            'k': params.get('k'),
            'n_regions': len(region_names),
            'tendency_metric': params['tendency_metric'],
            'top_n_chars': params['top_n_chars'],
            'execution_time_ms': execution_time,
            'metrics': metrics,
            'assignments': assignments,
            'cluster_profiles': cluster_profiles
        }

    def run_sampled_village_clustering(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行采样村庄聚类

        Args:
            params: 聚类参数

        Returns:
            聚类结果字典
        """
        start_time = time.time()

        # 枚举转字符串
        strategy = params['sampling_strategy']
        if hasattr(strategy, 'value'):
            strategy = strategy.value

        sample_size = params['sample_size']
        random_state = params['random_state']

        # 构建 WHERE 子句（过滤器）
        filter_config = params.get('filter') or {}
        if hasattr(filter_config, '__dict__'):
            filter_config = vars(filter_config)
        where_clauses = []
        filter_params = []
        if isinstance(filter_config, dict):
            if filter_config.get('cities'):
                placeholders = ','.join(['?' for _ in filter_config['cities']])
                where_clauses.append(f"{self._column(T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.CITY)} IN ({placeholders})")
                filter_params.extend(filter_config['cities'])
            if filter_config.get('counties'):
                placeholders = ','.join(['?' for _ in filter_config['counties']])
                where_clauses.append(f"{self._column(T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.COUNTY)} IN ({placeholders})")
                filter_params.extend(filter_config['counties'])
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        with self._connection() as conn:
            # 1) 先拿到候选 rowid（轻量列扫描，避免 ORDER BY RANDOM() 全表排序）
            id_query = f"SELECT rowid as _rid, {self._column(T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.COUNTY)} as county FROM {self._table(T.VILLAGE_FEATURES)}{where_sql}"
            id_df = pd.read_sql_query(id_query, conn, params=filter_params if filter_params else None)
            original_village_count = len(id_df)

            if id_df.empty:
                raise ValueError("No villages found for the given filters")

            if strategy in {"random", "stratified"}:
                sampled_ids_df = self._sample_villages(
                    id_df,
                    strategy,
                    sample_size,
                    random_state
                )
                sampled_rowids = sampled_ids_df["_rid"].astype(int).tolist()
                df_sampled = self._fetch_village_rows_by_rowids(conn, sampled_rowids)
            else:
                # spatial：先随机预取 3x 的候选，再做网格采样
                oversample = min(sample_size * 3, 50000, len(id_df))
                sampled_rowids = id_df.sample(
                    n=oversample,
                    random_state=random_state
                )["_rid"].astype(int).tolist()
                df_pre = self._fetch_village_rows_by_rowids(conn, sampled_rowids)
                df_sampled = self._sample_villages(df_pre, strategy, sample_size, random_state)

        logger.info(f"Sampled {len(df_sampled)} villages using {strategy} strategy (SQL-level)")

        # 3. 构建特征矩阵
        feature_columns = []
        feature_config = params['features']

        if feature_config.get('use_semantic', True):
            semantic_cols = [col for col in df_sampled.columns if col.startswith('sem_') and col.endswith('_pct')]
            feature_columns.extend(semantic_cols)

        if feature_config.get('use_morphology', True):
            feature_columns.append('name_length')

        X = df_sampled[feature_columns].values
        X = np.nan_to_num(X, nan=0.0)

        village_names = df_sampled['village_name'].tolist()

        # 4. 预处理
        if params['preprocessing']['standardize']:
            X = StandardScaler().fit_transform(X)

        if params['preprocessing']['use_pca']:
            n_components = min(params['preprocessing']['pca_n_components'], X.shape[1])
            pca = PCA(n_components=n_components)
            X = pca.fit_transform(X)

        # 5. 聚类
        algorithm = params['algorithm']
        labels = None

        if algorithm == 'kmeans':
            model = KMeans(
                n_clusters=params['k'],
                random_state=params['random_state'],
                n_init=10,
                max_iter=300
            )
            labels = model.fit_predict(X)

        elif algorithm == 'dbscan':
            eps = params.get('eps', 0.5)
            min_samples = params.get('min_samples', 5)
            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(X)

        elif algorithm == 'gmm':
            model = GaussianMixture(
                n_components=params['k'],
                random_state=params['random_state']
            )
            labels = model.fit_predict(X)

        # 6. 评估指标
        metrics = {}
        if len(set(labels)) > 1:
            metrics['silhouette_score'] = float(silhouette_score(X, labels))
            metrics['davies_bouldin_index'] = float(davies_bouldin_score(X, labels))
            metrics['calinski_harabasz_score'] = float(calinski_harabasz_score(X, labels))
        else:
            metrics['silhouette_score'] = 0.0
            metrics['davies_bouldin_index'] = 0.0
            metrics['calinski_harabasz_score'] = 0.0

        # 7. 聚类分配（只返回前1000个）
        assignments = []
        for i in range(min(len(village_names), 1000)):
            assignments.append({
                'village_name': village_names[i],
                'cluster_id': int(labels[i])
            })

        # 8. 聚类画像
        cluster_profiles = self._generate_cluster_profiles(X, labels, village_names)

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'run_id': f"sampled_villages_{int(time.time())}",
            'algorithm': algorithm,
            'k': params.get('k'),
            'original_village_count': int(original_village_count),
            'sampled_village_count': len(df_sampled),
            'sampling_strategy': params['sampling_strategy'],
            'execution_time_ms': execution_time,
            'metrics': metrics,
            'assignments': assignments,
            'cluster_profiles': cluster_profiles
        }

    def run_spatial_aware_clustering(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行空间感知聚类（对空间聚类结果进行二次聚类）

        Args:
            params: 聚类参数

        Returns:
            聚类结果字典
        """
        start_time = time.time()

        # 1. 解析空间聚类JSON
        X, cluster_ids, metadata = self._parse_spatial_json(params['spatial_run_id'])

        # 2. 特征选择
        feature_config = params.get('features', {})
        feature_indices = []

        # 语义特征 (0-8)
        if feature_config.get('use_semantic_profile', True):
            feature_indices.extend(range(0, 9))

        # 命名模式特征 (9-11)
        if feature_config.get('use_naming_patterns', True):
            feature_indices.extend(range(9, 12))

        # 地理特征 (12-13)
        if feature_config.get('use_geographic', True):
            feature_indices.extend(range(12, 14))

        # 聚类大小 (14)
        if feature_config.get('use_cluster_size', True):
            feature_indices.append(14)

        X_selected = X[:, feature_indices]

        # 3. 预处理
        if params['preprocessing']['standardize']:
            X_selected = StandardScaler().fit_transform(X_selected)
            logger.info("Features standardized")

        if params['preprocessing']['use_pca']:
            n_components = min(params['preprocessing']['pca_n_components'], X_selected.shape[1])
            pca = PCA(n_components=n_components)
            X_selected = pca.fit_transform(X_selected)
            logger.info(f"PCA applied: {X_selected.shape[1]} components")

        # 4. 聚类
        algorithm = params['algorithm']
        if hasattr(algorithm, 'value'):
            algorithm = algorithm.value
        labels = None

        if algorithm == 'kmeans':
            model = KMeans(
                n_clusters=params['k'],
                random_state=params['random_state'],
                n_init=10,
                max_iter=300
            )
            labels = model.fit_predict(X_selected)
            logger.info(f"KMeans clustering completed: k={params['k']}")

        elif algorithm == 'dbscan':
            eps = params.get('eps', 0.5)
            min_samples = params.get('min_samples', 5)
            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(X_selected)
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            logger.info(f"DBSCAN clustering completed: {n_clusters} clusters")

        elif algorithm == 'gmm':
            model = GaussianMixture(
                n_components=params['k'],
                random_state=params['random_state']
            )
            labels = model.fit_predict(X_selected)
            logger.info(f"GMM clustering completed: k={params['k']}")

        # 5. 评估指标
        metrics = {}
        if len(set(labels)) > 1:
            metrics['silhouette_score'] = float(silhouette_score(X_selected, labels))
            metrics['davies_bouldin_index'] = float(davies_bouldin_score(X_selected, labels))
            metrics['calinski_harabasz_score'] = float(calinski_harabasz_score(X_selected, labels))
        else:
            metrics['silhouette_score'] = 0.0
            metrics['davies_bouldin_index'] = 0.0
            metrics['calinski_harabasz_score'] = 0.0

        # 6. 聚类分配
        assignments = []
        for i in range(len(cluster_ids)):
            assignments.append({
                'spatial_cluster_id': int(cluster_ids[i]),
                'meta_cluster_id': int(labels[i])
            })

        # 7. 聚类画像
        cluster_profiles = self._generate_cluster_profiles(X_selected, labels, [str(cid) for cid in cluster_ids])

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'run_id': f"spatial_aware_{int(time.time())}",
            'algorithm': algorithm,
            'k': params.get('k'),
            'spatial_run_id': params['spatial_run_id'],
            'n_spatial_clusters': len(cluster_ids),
            'execution_time_ms': execution_time,
            'metrics': metrics,
            'assignments': assignments,
            'cluster_profiles': cluster_profiles
        }

    def run_hierarchical_clustering(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行层次聚类（市→县→镇三层嵌套）

        三级各自独立聚类，然后按真实地理父子关系组织树结构：
        - 每个城市只展示自己的县（非城市群所有县）
        - 每个县只展示自己的镇
        - 各级 cluster_id 来自各自独立的聚类结果

        Args:
            params: 聚类参数

        Returns:
            层次聚类结果字典
        """
        start_time = time.time()

        algorithm = params['algorithm']
        if hasattr(algorithm, 'value'):
            algorithm = algorithm.value

        base = {
            'algorithm': algorithm,
            'features': params['features'],
            'preprocessing': params['preprocessing'],
            'random_state': params['random_state']
        }

        # 1. 三级各自独立聚类（不按父级分组，保证 cluster_id 语义全局一致）
        city_result = self.run_clustering({**base, 'k': params['k_city'], 'region_level': 'city'})
        logger.info(f"City clustering: {city_result['n_regions']} cities → {params['k_city']} clusters")

        county_result = self.run_clustering({**base, 'k': params['k_county'], 'region_level': 'county'})
        logger.info(f"County clustering: {county_result['n_regions']} counties → {params['k_county']} clusters")

        try:
            township_result = self.run_clustering({**base, 'k': params['k_township'], 'region_level': 'township'})
            logger.info(f"Township clustering: {township_result['n_regions']} townships → {params['k_township']} clusters")
            township_to_cluster = {a['region_name']: a['cluster_id'] for a in township_result['assignments']}
            township_metrics = township_result['metrics']
        except Exception as e:
            logger.warning(f"Township clustering failed (skipped): {e}")
            township_to_cluster = {}
            township_metrics = {}

        city_to_cluster = {a['region_name']: a['cluster_id'] for a in city_result['assignments']}
        county_to_cluster = {a['region_name']: a['cluster_id'] for a in county_result['assignments']}

        # 2. 从数据库查询真实地理父子关系
        city_to_counties: Dict[str, List[str]] = {}
        county_to_townships: Dict[str, List[str]] = {}
        with self._connection() as conn:
            for city, county in conn.execute(f"SELECT DISTINCT {self._column(T.VILLAGES, C.VILLAGES.CITY)}, {self._column(T.VILLAGES, C.VILLAGES.COUNTY)} FROM {self._table(T.VILLAGES)} WHERE {self._column(T.VILLAGES, C.VILLAGES.CITY)} IS NOT NULL AND {self._column(T.VILLAGES, C.VILLAGES.COUNTY)} IS NOT NULL").fetchall():
                city_to_counties.setdefault(city, []).append(county)

            for county, town in conn.execute(f"SELECT DISTINCT {self._column(T.VILLAGES, C.VILLAGES.COUNTY)}, {self._column(T.VILLAGES, C.VILLAGES.TOWNSHIP)} FROM {self._table(T.VILLAGES)} WHERE {self._column(T.VILLAGES, C.VILLAGES.COUNTY)} IS NOT NULL AND {self._column(T.VILLAGES, C.VILLAGES.TOWNSHIP)} IS NOT NULL").fetchall():
                county_to_townships.setdefault(county, []).append(town)

        # 3. 构建层次树：每个城市只挂自己的县，每个县只挂自己的镇
        tree = []
        for city_assignment in sorted(city_result['assignments'], key=lambda a: a['region_name']):
            city_name = city_assignment['region_name']
            city_cluster_id = city_assignment['cluster_id']

            county_children = []
            for county_name in sorted(city_to_counties.get(city_name, [])):
                county_cluster_id = county_to_cluster.get(county_name)
                if county_cluster_id is None:
                    continue

                township_children = []
                for township_name in sorted(county_to_townships.get(county_name, [])):
                    tc = township_to_cluster.get(township_name)
                    if tc is None:
                        continue
                    township_children.append({
                        'level': 'township',
                        'region_name': township_name,
                        'cluster_id': tc
                    })

                county_children.append({
                    'level': 'county',
                    'region_name': county_name,
                    'cluster_id': county_cluster_id,
                    'children': township_children
                })

            tree.append({
                'level': 'city',
                'region_name': city_name,
                'cluster_id': city_cluster_id,
                'children': county_children
            })

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'run_id': f"hierarchical_{int(time.time())}",
            'algorithm': algorithm,
            'k_city': params['k_city'],
            'k_county': params['k_county'],
            'k_township': params['k_township'],
            'n_cities': len(city_result['assignments']),
            'n_counties': len(county_result['assignments']),
            'n_townships': len(township_to_cluster),
            'execution_time_ms': execution_time,
            'tree': tree,
            'metrics': {
                'city': city_result['metrics'],
                'county': county_result['metrics'],
                'township': township_metrics
            }
        }

    def _suggest_dbscan_params(
        self,
        n_clusters: int,
        n_noise: int,
        n_samples: int
    ) -> Dict[str, Any]:
        """
        根据聚类结果建议DBSCAN参数调整

        Args:
            n_clusters: 聚类数量
            n_noise: 噪声点数量
            n_samples: 样本总数

        Returns:
            参数建议字典
        """
        noise_ratio = n_noise / n_samples if n_samples > 0 else 0

        if n_clusters == 0:
            # 全是噪声点 - 参数太严格
            return {
                'status': 'too_strict',
                'message': '所有点都是噪声,参数过于严格',
                'suggestion': '增大eps(如+0.3)或减小min_samples(如-1)',
                'recommended_action': 'increase_eps'
            }
        elif n_clusters == 1 and n_noise == 0:
            # 只有一个聚类 - 参数太宽松
            return {
                'status': 'too_loose',
                'message': '所有点在同一聚类,参数过于宽松',
                'suggestion': '减小eps(如-0.3)或增大min_samples(如+1)',
                'recommended_action': 'decrease_eps'
            }
        elif noise_ratio > 0.3:
            # 噪声点过多
            return {
                'status': 'high_noise',
                'message': f'噪声点比例过高({noise_ratio:.1%})',
                'suggestion': '适当增大eps或减小min_samples',
                'recommended_action': 'increase_eps'
            }
        elif n_clusters > n_samples * 0.5:
            # 聚类过于碎片化
            return {
                'status': 'too_fragmented',
                'message': f'聚类过于碎片化({n_clusters}个聚类)',
                'suggestion': '增大eps以合并小聚类',
                'recommended_action': 'increase_eps'
            }
        else:
            # 参数合理
            return {
                'status': 'good',
                'message': f'聚类效果良好({n_clusters}个聚类,{noise_ratio:.1%}噪声)',
                'suggestion': '参数设置合理',
                'recommended_action': 'none'
            }



class SemanticEngine:
    """语义分析引擎"""

    def __init__(self, db_path: str, dbpath: str = DEFAULT_DATABASE_KEY):
        """
        初始化语义引擎

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.dbpath = dbpath
        self._db_pool = get_db_pool(db_path)

    @contextmanager
    def _connection(self):
        with self._db_pool.get_connection() as conn:
            yield conn

    def _table(self, logical_table: str) -> str:
        return qtable(self.dbpath, logical_table)

    def _column(self, logical_table: str, logical_column: str) -> str:
        return qcolumn(self.dbpath, logical_table, logical_column)

    def analyze_cooccurrence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析语义共现（使用实际表结构）

        Args:
            params: 分析参数（包含 detail: bool 参数）

        Returns:
            共现分析结果
        """
        start_time = time.time()

        # 根据 detail 参数选择表
        logical_table = table_variant(
            self.dbpath,
            TABLE_VARIANTS.SEMANTIC_BIGRAMS_BY_DETAIL,
            params.get('detail', False),
        )
        table = self._table(logical_table)

        # 从semantic_bigrams读取
        query = f"""
        SELECT
            {self._column(logical_table, C.SEMANTIC_BIGRAMS.CATEGORY1)} as category1,
            {self._column(logical_table, C.SEMANTIC_BIGRAMS.CATEGORY2)} as category2,
            {self._column(logical_table, C.SEMANTIC_BIGRAMS.FREQUENCY)} as cooccurrence_count,
            {self._column(logical_table, C.SEMANTIC_BIGRAMS.PMI)} as pmi
        FROM {table}
        WHERE {self._column(logical_table, C.SEMANTIC_BIGRAMS.FREQUENCY)} >= ?
        """

        with self._connection() as conn:
            df = pd.read_sql_query(query, conn, params=(params['min_cooccurrence'],))

        # 过滤类别
        if params.get('categories'):
            df = df[
                df['category1'].isin(params['categories']) |
                df['category2'].isin(params['categories'])
            ]

        # 识别显著模式（基于 PMI 阈值）
        # 使用 PMI > 0 作为显著性标准
        df_significant = df[df['pmi'] > 0]
        significant_pairs = df_significant.to_dict('records')

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'analysis_id': f"cooccur_{int(time.time())}",
            'region_name': params.get('region_name', 'all'),
            'execution_time_ms': execution_time,
            'cooccurrence_matrix': df.to_dict('records'),
            'significant_pairs': significant_pairs
        }

    def build_semantic_network(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建语义网络

        Args:
            params: 网络构建参数（包含 detail: bool 参数）

        Returns:
            语义网络结果
        """
        start_time = time.time()

        try:
            import networkx as nx
        except ImportError:
            logger.error("networkx not installed")
            return {
                'error': 'networkx library not installed',
                'execution_time_ms': 0
            }

        # 根据 detail 参数选择表
        logical_table = table_variant(
            self.dbpath,
            TABLE_VARIANTS.SEMANTIC_BIGRAMS_BY_DETAIL,
            params.get('detail', False),
        )
        table = self._table(logical_table)

        # 从semantic_bigrams读取边（使用PMI作为权重）
        query = f"""
        SELECT
            {self._column(logical_table, C.SEMANTIC_BIGRAMS.CATEGORY1)} as category1,
            {self._column(logical_table, C.SEMANTIC_BIGRAMS.CATEGORY2)} as category2,
            {self._column(logical_table, C.SEMANTIC_BIGRAMS.PMI)} as weight
        FROM {table}
        WHERE {self._column(logical_table, C.SEMANTIC_BIGRAMS.PMI)} >= ?
        """

        with self._connection() as conn:
            df = pd.read_sql_query(query, conn, params=(params['min_edge_weight'],))

        # 构建网络
        G = nx.Graph()

        for _, row in df.iterrows():
            if pd.notna(row['weight']):
                G.add_edge(row['category1'], row['category2'], weight=float(row['weight']))

        # 计算中心性指标
        nodes = []
        centrality_metrics = params.get('centrality_metrics', ['degree'])

        # 预计算中心性（避免重复计算）
        betweenness_dict = {}
        if 'betweenness' in centrality_metrics and len(G.nodes()) > 0:
            betweenness_dict = nx.betweenness_centrality(G)

        for node in G.nodes():
            node_data = {'id': node}

            if 'degree' in centrality_metrics:
                node_data['degree'] = G.degree(node)

            if 'betweenness' in centrality_metrics:
                node_data['betweenness'] = float(betweenness_dict.get(node, 0.0))

            nodes.append(node_data)

        # 提取边
        edges = [
            {'source': u, 'target': v, 'weight': float(d['weight'])}
            for u, v, d in G.edges(data=True)
        ]

        # 社区发现
        communities = []
        if len(G.nodes()) > 0:
            try:
                community_generator = nx.community.greedy_modularity_communities(G)
                communities = [
                    {'id': i, 'nodes': list(comm), 'size': len(comm)}
                    for i, comm in enumerate(community_generator)
                ]
            except Exception as e:
                logger.warning(f"Community detection failed: {e}")

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'network_id': f"network_{int(time.time())}",
            'node_count': len(nodes),
            'edge_count': len(edges),
            'execution_time_ms': execution_time,
            'nodes': nodes,
            'edges': edges,
            'communities': communities
        }


class FeatureEngine:
    """特征提取引擎"""

    def __init__(self, db_path: str, dbpath: str = DEFAULT_DATABASE_KEY):
        """
        初始化特征引擎

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.dbpath = dbpath
        self._db_pool = get_db_pool(db_path)
        self._feature_columns = None  # 缓存 PRAGMA table_info 结果

    @contextmanager
    def _connection(self):
        with self._db_pool.get_connection() as conn:
            yield conn

    def _table(self, logical_table: str) -> str:
        return qtable(self.dbpath, logical_table)

    def _column(self, logical_table: str, logical_column: str) -> str:
        return qcolumn(self.dbpath, logical_table, logical_column)

    def extract_features(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取村庄特征（使用 village_id 直接查询，性能最优）

        Args:
            params: 提取参数，villages 为 village_id 列表

        Returns:
            特征提取结果
        """
        start_time = time.time()

        feature_config = params.get('features', {})
        villages = params['villages']

        # 提取所有 village_id 并标准化格式（添加 v_ 前缀）
        village_ids = []
        for v in villages:
            vid = v['village_id']
            # 如果 ID 不以 v_ 开头，添加前缀
            if not vid.startswith('v_'):
                vid = f'v_{vid}'
            village_ids.append(vid)

        # 批量查询村庄特征（使用 IN 子句，性能最优）
        placeholders = ','.join(['?'] * len(village_ids))
        with self._connection() as conn:
            cursor = conn.cursor()

            # 获取列名（缓存 PRAGMA 结果）
            if self._feature_columns is None:
                cursor.execute(f"PRAGMA table_info({self._table(T.VILLAGE_FEATURES)})")
                self._feature_columns = [col[1] for col in cursor.fetchall()]
            columns = self._feature_columns

            batch_query = f"""
            SELECT * FROM {self._table(T.VILLAGE_FEATURES)}
            WHERE {self._column(T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.VILLAGE_ID)} IN ({placeholders})
            """
            cursor.execute(batch_query, village_ids)
            village_rows = cursor.fetchall()

            # 构建村庄数据字典（用于快速查找）
            village_data = {}
            for row in village_rows:
                row_dict = dict(zip(columns, row))
                village_data[row_dict[C.VILLAGE_FEATURES.VILLAGE_ID]] = row_dict

            # 如果启用 spatial，批量查询坐标
            spatial_data = {}
            if feature_config.get('spatial', False):
                spatial_query = f"""
                SELECT {self._column(T.VILLAGES, C.VILLAGES.VILLAGE_ID)} as village_id, {self._column(T.VILLAGES, C.VILLAGES.LONGITUDE)} as longitude, {self._column(T.VILLAGES, C.VILLAGES.LATITUDE)} as latitude
                FROM {self._table(T.VILLAGES)}
                WHERE {self._column(T.VILLAGES, C.VILLAGES.VILLAGE_ID)} IN ({placeholders})
                """
                cursor.execute(spatial_query, village_ids)
                for row in cursor.fetchall():
                    if row[1] is not None:  # 只保存有效坐标
                        spatial_data[row[0]] = {'longitude': row[1], 'latitude': row[2]}

            # 如果启用 character，批量查询字符特征
            character_data = {}
            if feature_config.get('character', False):
                towns = list(set([village_data[vid].get(C.VILLAGE_FEATURES.TOWN) for vid in village_ids if vid in village_data and village_data[vid].get(C.VILLAGE_FEATURES.TOWN)]))
                if towns:
                    town_placeholders = ','.join(['?'] * len(towns))
                    char_query = f"""
                    SELECT {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} as region_name, {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CHAR)} as char, {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.FREQUENCY)} as frequency
                    FROM {self._table(T.CHAR_REGIONAL_ANALYSIS)}
                    WHERE {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)} = ? AND {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} IN ({town_placeholders})
                    ORDER BY {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)}, {self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.FREQUENCY)} DESC
                    """
                    cursor.execute(char_query, [normalize_region_level(self.dbpath, T.CHAR_REGIONAL_ANALYSIS, "township")] + towns)

                    # 按乡镇分组，每个乡镇取 Top-20
                    current_town = None
                    current_chars = []
                    for row in cursor.fetchall():
                        town, char, freq = row
                        if town != current_town:
                            if current_town and current_chars:
                                character_data[current_town] = current_chars[:20]
                            current_town = town
                            current_chars = []
                        current_chars.append({'char': char, 'frequency': freq})
                    # 保存最后一个乡镇
                    if current_town and current_chars:
                        character_data[current_town] = current_chars[:20]

        # 构建特征列表
        features_list = []
        for village_id in village_ids:
            row_dict = village_data.get(village_id)

            if row_dict:
                feature_dict = {
                    'village_id': village_id,
                    'village_name': row_dict.get(C.VILLAGE_FEATURES.VILLAGE_NAME),
                    'city': row_dict.get(C.VILLAGE_FEATURES.CITY),
                    'county': row_dict.get(C.VILLAGE_FEATURES.COUNTY)
                }

                # 提取语义标签
                if feature_config.get('semantic_tags', True):
                    semantic_features = {}
                    for col in columns:
                        if col.startswith('sem_'):
                            semantic_features[col] = row_dict.get(col)
                    feature_dict['semantic_tags'] = semantic_features

                # 提取形态学特征
                if feature_config.get('morphology', True):
                    morphology_features = {
                        'name_length': row_dict.get(C.VILLAGE_FEATURES.NAME_LENGTH),
                        'suffix_1': row_dict.get(C.VILLAGE_FEATURES.SUFFIX_1),
                        'suffix_2': row_dict.get(C.VILLAGE_FEATURES.SUFFIX_2),
                        'suffix_3': row_dict.get(C.VILLAGE_FEATURES.SUFFIX_3),
                        'prefix_1': row_dict.get(C.VILLAGE_FEATURES.PREFIX_1),
                        'prefix_2': row_dict.get(C.VILLAGE_FEATURES.PREFIX_2),
                        'prefix_3': row_dict.get(C.VILLAGE_FEATURES.PREFIX_3)
                    }
                    feature_dict['morphology'] = morphology_features

                # 提取聚类信息
                if feature_config.get('clustering', True):
                    clustering_features = {
                        'kmeans_cluster_id': row_dict.get('kmeans_cluster_id'),
                        'dbscan_cluster_id': row_dict.get('dbscan_cluster_id'),
                        'gmm_cluster_id': row_dict.get('gmm_cluster_id')
                    }
                    feature_dict['clustering'] = clustering_features

                # 提取空间特征
                if feature_config.get('spatial', False):
                    if village_id in spatial_data:
                        feature_dict['spatial'] = spatial_data[village_id]
                    else:
                        feature_dict['spatial'] = {
                            'longitude': None,
                            'latitude': None
                        }

                # 提取字符特征
                if feature_config.get('character', False):
                    town = row_dict.get('town')
                    if town and town in character_data:
                        feature_dict['character'] = {
                            'top_chars': character_data[town]
                        }
                    else:
                        feature_dict['character'] = {
                            'top_chars': []
                        }

                features_list.append(feature_dict)

        execution_time = int((time.time() - start_time) * 1000)

        # 计算特征维度
        dimension = 0
        dimension_breakdown = {}

        if feature_config.get('semantic_tags', True):
            dimension += len(_SEM_NAMES)
            dimension_breakdown['semantic_tags'] = len(_SEM_NAMES)
        if feature_config.get('morphology', True):
            dimension += 7
            dimension_breakdown['morphology'] = 7
        if feature_config.get('clustering', True):
            dimension += 3
            dimension_breakdown['clustering'] = 3
        if feature_config.get('character', False):
            dimension += 20
            dimension_breakdown['character'] = 20
        if feature_config.get('spatial', False):
            dimension += 2
            dimension_breakdown['spatial'] = 2

        return {
            'extraction_id': f"extract_{int(time.time())}",
            'village_count': len(features_list),
            'feature_dimension': dimension,
            'dimension_breakdown': dimension_breakdown,
            'execution_time_ms': execution_time,
            'features': features_list
        }

    def aggregate_features(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        区域特征聚合（统计增强版）。

        不只返回原始百分比，还计算 lift（相对全局的提升度）、z-score（跨区域标准差）、
        多样性熵、结构画像，让每个区域的特征可解释、可比较。

        Args:
            params: 聚合参数

        Returns:
            特征聚合结果
        """
        import math
        start_time = time.time()

        region_level = params['region_level']
        region_names = params.get('region_names', [])
        feature_config = params.get('features', {})
        top_n = params.get('top_n', 10)

        cfg = region_level_config(self.dbpath, REGION_LEVEL_CONFIGS.COMPUTE_FEATURE_AGGREGATION, region_level)
        group_cols = cfg["group_cols"]
        region_col = group_cols[-1]

        sem_names = _SEM_NAMES

        with self._connection() as conn:
            vf_table = self._table(T.VILLAGE_FEATURES)
            vss_table = self._table(T.VILLAGE_SEMANTIC_STRUCTURE)
            gcp = [self._column(T.VILLAGE_FEATURES, g) for g in group_cols]

            # ---- filter helpers ----
            def _region_filter():
                if not region_names:
                    return "", []
                fc = self._column(T.VILLAGE_FEATURES, region_col)
                ph = ','.join(['?' for _ in region_names])
                return f" WHERE {fc} IN ({ph})", list(region_names)

            where, where_params = _region_filter()

            # ==== 1. global baseline — aggregate over ALL villages ====
            global_total = conn.execute(f"SELECT COUNT(*) FROM {vf_table}").fetchone()[0]

            # 合并 9 个独立 SUM 查询为 1 次全表扫描
            sem_sum_exprs = [f"SUM({self._column(T.VILLAGE_FEATURES, semantic_feature_column(n))}) AS sem_{n}" for n in sem_names]
            sem_row = conn.execute(f"SELECT {', '.join(sem_sum_exprs)} FROM {vf_table}").fetchone()
            global_sem_sums = {}
            for i, n in enumerate(sem_names):
                global_sem_sums[n] = sem_row[i] or 0

            sfx_col = self._column(T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.SUFFIX_1)
            global_suffix_total = conn.execute(
                f"SELECT COUNT(*) FROM {vf_table} WHERE {sfx_col} IS NOT NULL AND {sfx_col} != ''"
            ).fetchone()[0]
            global_suffix_counts: dict = {}
            for row in conn.execute(
                f"SELECT {sfx_col}, COUNT(*) as cnt FROM {vf_table} WHERE {sfx_col} IS NOT NULL AND {sfx_col} != '' GROUP BY {sfx_col}"
            ).fetchall():
                global_suffix_counts[row[0]] = row[1]

            # ==== 2. per-region basic stats ====
            sem_cols = [self._column(T.VILLAGE_FEATURES, semantic_feature_column(n)) for n in sem_names]
            sem_sum_exprs = [f"SUM({c}) AS sem_{n}_cnt" for c, n in zip(sem_cols, sem_names)]
            select_parts = gcp + [
                "COUNT(*) AS total_villages",
                f"AVG({self._column(T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.NAME_LENGTH)}) AS avg_name_length",
            ] + sem_sum_exprs

            query = f"SELECT {', '.join(select_parts)} FROM {vf_table}{where} GROUP BY {', '.join(gcp)}"
            df = pd.read_sql_query(query, conn, params=where_params)

            for g in group_cols:
                physical = self._column(T.VILLAGE_FEATURES, g).strip('"')
                if physical in df.columns and physical != g:
                    df[g] = df[physical]

            df['region_key'] = df.apply(lambda r: tuple(r[g] for g in group_cols), axis=1)

            # ==== 3. per-region suffix distribution ====
            region_suffix_counts: dict = {}
            sfx_query = f"""
                SELECT {', '.join(gcp)}, {sfx_col}, COUNT(*) as cnt
                FROM {vf_table}
                WHERE {sfx_col} IS NOT NULL AND {sfx_col} != ''{f' AND {self._column(T.VILLAGE_FEATURES, region_col)} IN ({",".join(["?"]*len(region_names))})' if region_names else ''}
                GROUP BY {', '.join(gcp)}, {sfx_col}
            """
            for row in conn.execute(sfx_query, region_names if region_names else []).fetchall():
                rk = tuple(row[:len(group_cols)])
                entry = region_suffix_counts.setdefault(rk, {})
                entry[row[len(group_cols)]] = row[-1]

            # ==== 4. structure profile from village_semantic_structure ====
            structure_data: dict = {}
            if feature_config.get('structure_profile', True):
                try:
                    vss_vid = self._column(T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.VILLAGE_ID)
                    vf_vid = self._column(T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.VILLAGE_ID)
                    struct_metrics = [
                        C.VILLAGE_SEMANTIC_STRUCTURE.HAS_MODIFIER,
                        C.VILLAGE_SEMANTIC_STRUCTURE.HAS_HEAD,
                        C.VILLAGE_SEMANTIC_STRUCTURE.HAS_SETTLEMENT,
                    ]
                    struct_select = [f'SUM({self._column(T.VILLAGE_SEMANTIC_STRUCTURE, m)}) AS {m}' for m in struct_metrics]
                    st_query = f"""
                        SELECT {', '.join([f'vf.{c}' for c in gcp])}, COUNT(*) as cnt, {', '.join(struct_select)}
                        FROM {vss_table} vss
                        JOIN {vf_table} vf ON vss.{vss_vid} = vf.{vf_vid}
                        {f"WHERE {self._column(T.VILLAGE_FEATURES, region_col)} IN ({','.join(['?']*len(region_names))})" if region_names else ''}
                        GROUP BY {', '.join([f'vf.{c}' for c in gcp])}
                    """
                    for row in conn.execute(st_query, region_names if region_names else []).fetchall():
                        rk = tuple(row[:len(group_cols)])
                        total = row[len(group_cols)]
                        entry = {}
                        for i, m in enumerate(struct_metrics):
                            entry[m] = {"count": row[len(group_cols) + 1 + i] or 0,
                                         "pct": round((row[len(group_cols) + 1 + i] or 0) * 100.0 / total, 2) if total else 0}
                        entry["total"] = total
                        structure_data[rk] = entry
                except Exception:
                    pass

            # ==== 5. distinctive characters from char_regional_analysis ====
            char_data: dict = {}
            if feature_config.get('distinctive_chars', True):
                try:
                    cr_table = self._table(T.CHAR_REGIONAL_ANALYSIS)
                    cr_level = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)
                    cr_region = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)
                    cr_char = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CHAR)
                    cr_lift = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.LIFT)
                    cr_zscore = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.Z_SCORE)
                    cr_freq = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.FREQUENCY)
                    cr_rank = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.RANK_WITHIN_REGION)

                    if region_level == 'city':
                        cr_name_col = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CITY)
                    elif region_level == 'township':
                        cr_name_col = self._column(T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.TOWNSHIP)
                    else:
                        cr_name_col = cr_region

                    ch_query = f"""
                        SELECT {cr_name_col}, {cr_char}, {cr_lift}, {cr_zscore}, {cr_freq}, {cr_rank}
                        FROM {cr_table}
                        WHERE {cr_level} = ?
                          AND {cr_rank} <= ?
                        ORDER BY {cr_name_col}, {cr_rank}
                    """
                    for row in conn.execute(ch_query, (normalize_region_level(self.dbpath, T.CHAR_REGIONAL_ANALYSIS, region_level), top_n * 2)).fetchall():
                        rn = row[0]
                        entry = char_data.setdefault(rn, [])
                        if len(entry) < top_n:
                            entry.append({
                                'char': row[1],
                                'lift': round(row[2], 3) if row[2] is not None else None,
                                'z_score': round(row[3], 3) if row[3] is not None else None,
                                'frequency': round(row[4], 3) if row[4] is not None else None,
                            })
                except Exception:
                    pass

            # ==== 6. cluster distribution (filtered by active run_id) ====
            cluster_data: dict = {}
            if feature_config.get('cluster_distribution', True):
                try:
                    ar_table = self._table(T.ACTIVE_RUN_IDS)
                    ar_type_col = self._column(T.ACTIVE_RUN_IDS, C.ACTIVE_RUN_IDS.ANALYSIS_TYPE)
                    ar_runid_col = self._column(T.ACTIVE_RUN_IDS, C.ACTIVE_RUN_IDS.RUN_ID)
                    row = conn.execute(
                        f"SELECT {ar_runid_col} FROM {ar_table} WHERE {ar_type_col} = ?",
                        (run_id_analysis_type(self.dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS),)
                    ).fetchone()
                    spatial_run_id = row[0] if row else None

                    if spatial_run_id:
                        ca_table = self._table(T.VILLAGE_CLUSTER_ASSIGNMENTS)
                        ca_runid_col = self._column(T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.RUN_ID)
                        ca_col = self._column(T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.CLUSTER_ID)
                        ca_vid = self._column(T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.VILLAGE_ID)
                        cl_query = f"""
                            SELECT {', '.join([f'vf.{c}' for c in gcp])}, ca.{ca_col}, COUNT(*) as cnt
                            FROM {ca_table} ca
                            JOIN {vf_table} vf ON ca.{ca_vid} = vf.{vf_vid}
                            WHERE ca.{ca_runid_col} = ?
                            GROUP BY {', '.join([f'vf.{c}' for c in gcp])}, ca.{ca_col}
                        """
                        for row in conn.execute(cl_query, (spatial_run_id,)).fetchall():
                            rk = tuple(row[:len(group_cols)])
                            cd = cluster_data.setdefault(rk, {})
                            cd[str(row[len(group_cols)])] = row[-1]
                except Exception:
                    pass

        # ======== Build result ========
        aggregates = []
        region_list: list[dict] = []  # collect for z-score computation

        for _, row in df.iterrows():
            rk = row['region_key']
            total = int(row['total_villages'])

            if region_level == 'township':
                region_name = f"{row['city']} > {row['county']} > {row['town']}"
            elif region_level == 'county':
                region_name = f"{row['city']} > {row['county']}"
            else:
                region_name = row[region_col]

            agg = {
                'region_name': region_name,
                'total_villages': total,
                'avg_name_length': round(float(row['avg_name_length']), 2) if pd.notna(row['avg_name_length']) else None,
            }
            # Convert row to plain dict — pandas iterrows() reuses the Series object
            z_vals = {'avg_name_length': agg['avg_name_length']}
            for n in sem_names:
                cnt_key = f'sem_{n}_cnt'
                val = int(row[cnt_key]) if pd.notna(row.get(cnt_key)) else 0
                z_vals[cnt_key] = val
            region_list.append({'key': rk, 'name': region_name, 'agg': agg, 'z_vals': z_vals})

            # --- semantic profile with lift ---
            if feature_config.get('semantic_distribution', True):
                sem_profile = {}
                for n in sem_names:
                    cnt = int(row[f'sem_{n}_cnt']) if pd.notna(row[f'sem_{n}_cnt']) else 0
                    region_pct = round(cnt * 100.0 / total, 2) if total else 0.0
                    global_pct = round(global_sem_sums[n] * 100.0 / global_total, 2) if global_total else 0.0
                    lift = round(region_pct / global_pct, 3) if global_pct > 0 else None
                    sem_profile[n] = {
                        'count': cnt,
                        'pct': region_pct,
                        'global_pct': global_pct,
                        'lift': lift,
                    }
                agg['semantic_profile'] = sem_profile

            # --- suffix distribution with lift ---
            if feature_config.get('morphology_freq', True):
                sfx = region_suffix_counts.get(rk, {})
                region_total = sum(sfx.values())
                sfx_list = []
                for suffix, cnt in sorted(sfx.items(), key=lambda x: -x[1]):
                    pct = round(cnt * 100.0 / region_total, 2) if region_total else 0.0
                    global_pct = round(global_suffix_counts.get(suffix, 0) * 100.0 / global_suffix_total, 2) if global_suffix_total else 0.0
                    lift = round(pct / global_pct, 3) if global_pct > 0 else None
                    sfx_list.append({'suffix': suffix, 'count': cnt, 'pct': pct, 'global_pct': global_pct, 'lift': lift})
                agg['suffixes'] = sfx_list[:top_n]
                # distinctive = sorted by lift descending
                agg['distinctive_suffixes'] = sorted(sfx_list, key=lambda x: -(x['lift'] or 0))[:top_n]

            # --- diversity ---
            if feature_config.get('diversity_metrics', True):
                # semantic entropy
                sem_probs = [max(agg['semantic_profile'][n]['pct'] / 100.0, 0.001) for n in sem_names] if 'semantic_profile' in agg else []
                sem_entropy = -sum(p * math.log(p) for p in sem_probs) if sem_probs else None

                # suffix entropy
                sfx = region_suffix_counts.get(rk, {})
                sfx_total = sum(sfx.values()) or 1
                sfx_probs = [max(c / sfx_total, 0.001) for c in sfx.values()]
                sfx_entropy = -sum(p * math.log(p) for p in sfx_probs) if sfx_probs else None

                agg['diversity'] = {
                    'semantic_entropy': round(sem_entropy, 4) if sem_entropy else None,
                    'suffix_entropy': round(sfx_entropy, 4) if sfx_entropy else None,
                    'unique_suffixes': len(sfx),
                }

            # --- structure_profile ---
            if feature_config.get('structure_profile', True) and rk in structure_data:
                agg['structure_profile'] = structure_data[rk]

            # --- distinctive_chars ---
            if feature_config.get('distinctive_chars', True):
                agg['distinctive_chars'] = char_data.get(region_name, [])

            # --- cluster_distribution ---
            if feature_config.get('cluster_distribution', True):
                agg['cluster_distribution'] = cluster_data.get(rk, {})

            aggregates.append(agg)

        # ==== z-scores across requested regions ====
        z_metric_names = ['avg_name_length'] + [f'sem_{n}_pct' for n in sem_names]
        from statistics import mean, stdev
        for mi, metric_name in enumerate(z_metric_names):
            vals = []
            for r in region_list:
                if metric_name == 'avg_name_length':
                    v = r['z_vals']['avg_name_length']
                else:
                    # metric_name like 'sem_mountain_pct' → cnt_key like 'sem_mountain_cnt'
                    cnt_key = metric_name.replace('_pct', '_cnt')
                    total = r['agg']['total_villages']
                    cnt = r['z_vals'].get(cnt_key, 0)
                    v = round(cnt * 100.0 / total, 2) if total else 0.0
                if v is not None:
                    vals.append((r, v))
            if len(vals) >= 3:
                vs = [v for _, v in vals]
                m, s = mean(vs), stdev(vs)
                if s > 0:
                    for r, v in vals:
                        r['agg'].setdefault('z_scores', {})[metric_name] = round((v - m) / s, 3)

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'aggregation_id': f"aggregate_{int(time.time())}",
            'region_level': region_level,
            'region_count': len(aggregates),
            'execution_time_ms': execution_time,
            'aggregates': aggregates
        }
