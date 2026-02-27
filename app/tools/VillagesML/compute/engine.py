"""
计算引擎模块 (Compute Engine)

提供核心计算功能：
- ClusteringEngine: 聚类分析
- SemanticEngine: 语义分析
- FeatureEngine: 特征提取
"""

import time
import sqlite3
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

logger = logging.getLogger(__name__)


class ClusteringEngine:
    """聚类计算引擎"""

    def __init__(self, db_path: str):
        """
        初始化聚类引擎

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.feature_cache = {}  # 特征矩阵缓存

    def get_regional_features(
        self,
        region_level: str,
        feature_config: Dict[str, Any],
        region_filter: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[str]]:
        """
        获取区域特征矩阵（使用实际表结构）

        Args:
            region_level: 区域级别 (city/county/township)
            feature_config: 特征配置
            region_filter: 区域过滤器

        Returns:
            (特征矩阵, 区域名称列表)
        """
        cache_key = f"{region_level}:{hash(str(feature_config))}:{hash(str(region_filter))}"

        if cache_key in self.feature_cache:
            logger.info(f"Using cached features for {region_level}")
            return self.feature_cache[cache_key]

        conn = sqlite3.connect(self.db_path)

        # 根据region_level选择正确的表
        table_map = {
            'city': 'city_aggregates',
            'county': 'county_aggregates',
            'township': 'town_aggregates'
        }
        table_name = table_map.get(region_level, 'county_aggregates')

        # 1. 读取区域聚合表
        query = f"SELECT * FROM {table_name}"
        df_regional = pd.read_sql_query(query, conn)

        # 确定区域名称列
        region_col = 'city' if region_level == 'city' else 'county'

        # 过滤区域
        if region_filter:
            df_regional = df_regional[df_regional[region_col].isin(region_filter)]

        region_names = df_regional[region_col].tolist()

        # 2. 构建特征向量
        feature_columns = []

        if feature_config.get('use_semantic', True):
            # 语义百分比特征（9个）
            semantic_cols = [
                'sem_mountain_pct', 'sem_water_pct', 'sem_settlement_pct',
                'sem_direction_pct', 'sem_clan_pct', 'sem_symbolic_pct',
                'sem_agriculture_pct', 'sem_vegetation_pct', 'sem_infrastructure_pct'
            ]
            feature_columns.extend([col for col in semantic_cols if col in df_regional.columns])

        if feature_config.get('use_morphology', True):
            # 形态学特征
            feature_columns.append('avg_name_length')

        if feature_config.get('use_diversity', True):
            # 多样性特征（使用村庄总数作为代理）
            feature_columns.append('total_villages')

        # 提取特征矩阵
        X = df_regional[feature_columns].values

        # 处理缺失值
        X = np.nan_to_num(X, nan=0.0)

        conn.close()

        # 缓存结果
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
        conn = sqlite3.connect(self.db_path)

        # 映射region_level到表中的列名
        level_map = {
            'city': 'city',
            'county': 'county',
            'township': 'town'
        }
        region_col = level_map.get(region_level, 'county')

        # 使用窗口函数选择每个区域的top N字符
        query = f"""
        SELECT region, character, {tendency_metric}
        FROM (
            SELECT
                {region_col} as region,
                character,
                {tendency_metric},
                ROW_NUMBER() OVER (PARTITION BY {region_col} ORDER BY {tendency_metric} DESC) as rn
            FROM char_regional_analysis
            WHERE {region_col} IS NOT NULL
        )
        WHERE rn <= ?
        """

        params = [top_n_chars]

        # 添加区域过滤
        if region_filter:
            placeholders = ','.join(['?' for _ in region_filter])
            query = query.replace("WHERE rn <=", f"AND region IN ({placeholders}) WHERE rn <=")
            params = region_filter + params

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        # Pivot操作：region × character矩阵
        pivot_df = df.pivot(index='region', columns='character', values=tendency_metric)

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
        conn = sqlite3.connect(self.db_path)

        query = """
        SELECT
            cluster_id,
            village_count,
            semantic_profile_json,
            naming_patterns_json,
            centroid_lon,
            centroid_lat
        FROM spatial_clusters
        WHERE run_id = ?
        """

        df = pd.read_sql_query(query, conn, params=[run_id])
        conn.close()

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
                for category in ['mountain', 'water', 'settlement', 'direction', 'clan', 'symbolic', 'agriculture', 'vegetation', 'infrastructure']:
                    feature_vec.append(semantic_profile.get(f'{category}_pct', 0.0))
            except:
                feature_vec.extend([0.0] * 9)

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
            feature_vec.append(row['village_count'] if pd.notna(row['village_count']) else 0)

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
            eps = params.get('eps', 0.5)
            min_samples = params.get('min_samples', 5)
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

        conn = sqlite3.connect(self.db_path)

        # 1. 查询村庄特征
        query = "SELECT * FROM village_features"
        where_clauses = []
        query_params = []

        # 应用过滤器
        filter_config = params.get('filter', {})
        if filter_config:
            if filter_config.get('cities'):
                placeholders = ','.join(['?' for _ in filter_config['cities']])
                where_clauses.append(f"city IN ({placeholders})")
                query_params.extend(filter_config['cities'])

            if filter_config.get('counties'):
                placeholders = ','.join(['?' for _ in filter_config['counties']])
                where_clauses.append(f"county IN ({placeholders})")
                query_params.extend(filter_config['counties'])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        df = pd.read_sql_query(query, conn, params=query_params if query_params else None)
        conn.close()

        original_count = len(df)
        logger.info(f"Loaded {original_count} villages")

        # 2. 采样
        df_sampled = self._sample_villages(
            df,
            params['sampling_strategy'],
            params['sample_size'],
            params['random_state']
        )

        logger.info(f"Sampled {len(df_sampled)} villages using {params['sampling_strategy']} strategy")

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
            'original_village_count': original_count,
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

        Args:
            params: 聚类参数

        Returns:
            层次聚类结果字典
        """
        start_time = time.time()

        # 1. City-level聚类
        city_params = {
            'algorithm': params['algorithm'],
            'k': params['k_city'],
            'region_level': 'city',
            'features': params['features'],
            'preprocessing': params['preprocessing'],
            'random_state': params['random_state']
        }

        city_result = self.run_clustering(city_params)
        logger.info(f"City-level clustering completed: {params['k_city']} clusters")

        # 2. 构建city cluster到city的映射
        city_to_cluster = {}
        for assignment in city_result['assignments']:
            city_to_cluster[assignment['region_name']] = assignment['cluster_id']

        # 3. County-level聚类（对每个city cluster）
        county_results = {}
        for city_cluster_id in range(params['k_city']):
            # 找到属于这个city cluster的所有城市
            cities_in_cluster = [city for city, cid in city_to_cluster.items() if cid == city_cluster_id]

            if len(cities_in_cluster) == 0:
                continue

            # 对这些城市的县进行聚类
            county_params = {
                'algorithm': params['algorithm'],
                'k': min(params['k_county'], len(cities_in_cluster) * 10),  # 动态调整k
                'region_level': 'county',
                'region_filter': cities_in_cluster,
                'features': params['features'],
                'preprocessing': params['preprocessing'],
                'random_state': params['random_state']
            }

            try:
                county_result = self.run_clustering(county_params)
                county_results[city_cluster_id] = county_result
                logger.info(f"County-level clustering for city cluster {city_cluster_id}: {county_result['n_regions']} counties")
            except Exception as e:
                logger.warning(f"County clustering failed for city cluster {city_cluster_id}: {e}")
                county_results[city_cluster_id] = {'assignments': [], 'skipped': True}

        # 4. Township-level聚类（对每个county cluster）
        township_results = {}
        for city_cluster_id, county_result in county_results.items():
            if county_result.get('skipped'):
                continue

            # 构建county到cluster的映射
            county_to_cluster = {}
            for assignment in county_result['assignments']:
                county_to_cluster[assignment['region_name']] = assignment['cluster_id']

            for county_cluster_id in range(county_result.get('k', 0)):
                # 找到属于这个county cluster的所有县
                counties_in_cluster = [county for county, cid in county_to_cluster.items() if cid == county_cluster_id]

                if len(counties_in_cluster) == 0:
                    continue

                # 对这些县的镇进行聚类
                township_params = {
                    'algorithm': params['algorithm'],
                    'k': min(params['k_township'], len(counties_in_cluster) * 20),  # 动态调整k
                    'region_level': 'township',
                    'region_filter': counties_in_cluster,
                    'features': params['features'],
                    'preprocessing': params['preprocessing'],
                    'random_state': params['random_state']
                }

                try:
                    township_result = self.run_clustering(township_params)
                    key = (city_cluster_id, county_cluster_id)
                    township_results[key] = township_result
                    logger.info(f"Township-level clustering for county cluster {key}: {township_result['n_regions']} townships")
                except Exception as e:
                    logger.warning(f"Township clustering failed for county cluster {key}: {e}")
                    township_results[key] = {'assignments': [], 'skipped': True}

        # 5. 构建层次树
        tree = []
        for city_assignment in city_result['assignments']:
            city_name = city_assignment['region_name']
            city_cluster_id = city_assignment['cluster_id']

            city_node = {
                'level': 'city',
                'region_name': city_name,
                'cluster_id': city_cluster_id,
                'children': []
            }

            # 添加county节点
            if city_cluster_id in county_results and not county_results[city_cluster_id].get('skipped'):
                county_result = county_results[city_cluster_id]
                for county_assignment in county_result['assignments']:
                    county_name = county_assignment['region_name']
                    county_cluster_id = county_assignment['cluster_id']

                    county_node = {
                        'level': 'county',
                        'region_name': county_name,
                        'cluster_id': county_cluster_id,
                        'parent_cluster_id': city_cluster_id,
                        'children': []
                    }

                    # 添加township节点
                    key = (city_cluster_id, county_cluster_id)
                    if key in township_results and not township_results[key].get('skipped'):
                        township_result = township_results[key]
                        for township_assignment in township_result['assignments']:
                            township_name = township_assignment['region_name']
                            township_cluster_id = township_assignment['cluster_id']

                            township_node = {
                                'level': 'township',
                                'region_name': township_name,
                                'cluster_id': township_cluster_id,
                                'parent_cluster_id': county_cluster_id
                            }

                            county_node['children'].append(township_node)

                    city_node['children'].append(county_node)

            tree.append(city_node)

        execution_time = int((time.time() - start_time) * 1000)

        # 6. 汇总指标
        total_metrics = {
            'city_metrics': city_result['metrics'],
            'county_clusters_count': len([r for r in county_results.values() if not r.get('skipped')]),
            'township_clusters_count': len([r for r in township_results.values() if not r.get('skipped')])
        }

        return {
            'run_id': f"hierarchical_{int(time.time())}",
            'algorithm': params['algorithm'],
            'k_city': params['k_city'],
            'k_county': params['k_county'],
            'k_township': params['k_township'],
            'execution_time_ms': execution_time,
            'tree': tree,
            'metrics': total_metrics
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

    def __init__(self, db_path: str):
        """
        初始化语义引擎

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path

    def analyze_cooccurrence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析语义共现（使用实际表结构）

        Args:
            params: 分析参数（包含 detail: bool 参数）

        Returns:
            共现分析结果
        """
        start_time = time.time()

        conn = sqlite3.connect(self.db_path)

        # 根据 detail 参数选择表
        table_name = "semantic_bigrams_detailed" if params.get('detail', False) else "semantic_bigrams"

        # 从semantic_bigrams读取
        query = f"""
        SELECT
            category1, category2, frequency as cooccurrence_count,
            pmi
        FROM {table_name}
        WHERE frequency >= ?
        """

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

        conn.close()

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

        conn = sqlite3.connect(self.db_path)

        # 根据 detail 参数选择表
        table_name = "semantic_bigrams_detailed" if params.get('detail', False) else "semantic_bigrams"

        # 从semantic_bigrams读取边（使用PMI作为权重）
        query = f"""
        SELECT category1, category2, pmi as weight
        FROM {table_name}
        WHERE pmi >= ?
        """

        df = pd.read_sql_query(query, conn, params=(params['min_edge_weight'],))
        conn.close()

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

    def __init__(self, db_path: str):
        """
        初始化特征引擎

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path

    def extract_features(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取村庄特征（使用实际表结构）

        Args:
            params: 提取参数

        Returns:
            特征提取结果
        """
        start_time = time.time()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取列名
        cursor.execute("PRAGMA table_info(village_features)")
        columns = [col[1] for col in cursor.fetchall()]

        features_list = []
        feature_config = params.get('features', {})

        for village in params['villages']:
            # 查询村庄特征
            query = """
            SELECT * FROM village_features
            WHERE village_name = ?
            """

            # 如果提供了城市/县区过滤
            if 'city' in village:
                query += " AND city = ?"
                cursor.execute(query, (village['name'], village['city']))
            else:
                cursor.execute(query, (village['name'],))

            row = cursor.fetchone()

            if row:
                # 构建特征字典
                row_dict = dict(zip(columns, row))
                feature_dict = {
                    'village_name': village['name'],
                    'city': row_dict.get('city'),
                    'county': row_dict.get('county')
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
                        'name_length': row_dict.get('name_length'),
                        'suffix_1': row_dict.get('suffix_1'),
                        'suffix_2': row_dict.get('suffix_2'),
                        'suffix_3': row_dict.get('suffix_3'),
                        'prefix_1': row_dict.get('prefix_1'),
                        'prefix_2': row_dict.get('prefix_2'),
                        'prefix_3': row_dict.get('prefix_3')
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

                features_list.append(feature_dict)

        conn.close()

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'extraction_id': f"extract_{int(time.time())}",
            'village_count': len(features_list),
            'execution_time_ms': execution_time,
            'features': features_list
        }

    def aggregate_features(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        聚合区域特征

        Args:
            params: 聚合参数

        Returns:
            特征聚合结果
        """
        start_time = time.time()

        conn = sqlite3.connect(self.db_path)

        region_level = params['region_level']
        region_names = params.get('region_names', [])
        feature_config = params.get('features', {})
        top_n = params.get('top_n', 10)

        # 选择正确的聚合表
        table_map = {
            'city': 'city_aggregates',
            'county': 'county_aggregates',
            'township': 'town_aggregates'
        }
        table_name = table_map.get(region_level, 'county_aggregates')

        region_col_map = {
            'city': 'city',
            'county': 'county',
            'township': 'town'
        }
        region_col = region_col_map.get(region_level, 'county')

        # 构建查询
        query = f"SELECT * FROM {table_name}"
        if region_names:
            placeholders = ','.join(['?' for _ in region_names])
            query += f" WHERE {region_col} IN ({placeholders})"
            df = pd.read_sql_query(query, conn, params=region_names)
        else:
            df = pd.read_sql_query(query, conn)

        aggregates = []

        for _, row in df.iterrows():
            # 构建区域名称（包含完整路径）
            if region_level == 'township':
                region_name = f"{row['city']} > {row['county']} > {row['town']}"
            elif region_level == 'county':
                region_name = f"{row['city']} > {row['county']}"
            else:
                region_name = row[region_col]

            aggregate_dict = {
                'region_name': region_name,
                'total_villages': row.get('total_villages', 0)
            }

            # 语义分布
            if feature_config.get('semantic_distribution', True):
                semantic_dist = {}
                for col in df.columns:
                    if col.endswith('_pct'):
                        semantic_dist[col] = float(row[col]) if pd.notna(row[col]) else 0.0
                aggregate_dict['semantic_distribution'] = semantic_dist

            # 形态学频率（从JSON字段解析）
            if feature_config.get('morphology_freq', True):
                try:
                    import json
                    top_suffixes = json.loads(row.get('top_suffixes_json', '[]'))
                    top_prefixes = json.loads(row.get('top_prefixes_json', '[]'))
                    aggregate_dict['top_suffixes'] = top_suffixes[:top_n]
                    aggregate_dict['top_prefixes'] = top_prefixes[:top_n]
                except Exception as e:
                    logger.warning(f"Failed to parse JSON: {e}")
                    aggregate_dict['top_suffixes'] = []
                    aggregate_dict['top_prefixes'] = []

            # 聚类分布（从JSON字段解析）
            if feature_config.get('cluster_distribution', True):
                try:
                    import json
                    cluster_dist = json.loads(row.get('cluster_distribution_json', '{}'))
                    aggregate_dict['cluster_distribution'] = cluster_dist
                except Exception as e:
                    logger.warning(f"Failed to parse cluster distribution: {e}")
                    aggregate_dict['cluster_distribution'] = {}

            aggregates.append(aggregate_dict)

        conn.close()

        execution_time = int((time.time() - start_time) * 1000)

        return {
            'aggregation_id': f"aggregate_{int(time.time())}",
            'region_level': region_level,
            'region_count': len(aggregates),
            'execution_time_ms': execution_time,
            'aggregates': aggregates
        }
