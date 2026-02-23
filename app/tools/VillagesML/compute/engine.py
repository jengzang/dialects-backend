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
            model = DBSCAN(eps=0.5, min_samples=5)
            labels = model.fit_predict(X)
            logger.info(f"DBSCAN clustering completed: {len(set(labels))} clusters")

        elif algorithm == 'gmm':
            model = GaussianMixture(
                n_components=params['k'],
                random_state=params['random_state']
            )
            labels = model.fit_predict(X)
            logger.info(f"GMM clustering completed: k={params['k']}")

        # 4. 评估指标
        metrics = {}
        if len(set(labels)) > 1:  # 至少2个聚类
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

        return {
            'run_id': f"online_clustering_{int(time.time())}",
            'algorithm': algorithm,
            'k': params.get('k'),
            'n_regions': len(region_names),
            'execution_time_ms': execution_time,
            'metrics': metrics,
            'assignments': assignments,
            'cluster_profiles': cluster_profiles
        }

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
            params: 分析参数

        Returns:
            共现分析结果
        """
        start_time = time.time()

        conn = sqlite3.connect(self.db_path)

        # 从semantic_bigrams和semantic_pmi读取
        query = """
        SELECT
            b.cat1, b.cat2, b.count as cooccurrence_count,
            p.pmi, p.chi2_statistic, p.p_value
        FROM semantic_bigrams b
        LEFT JOIN semantic_pmi p ON b.cat1 = p.cat1 AND b.cat2 = p.cat2
        WHERE b.count >= ?
        """

        df = pd.read_sql_query(query, conn, params=(params['min_cooccurrence'],))

        # 过滤类别
        if params.get('categories'):
            df = df[
                df['cat1'].isin(params['categories']) |
                df['cat2'].isin(params['categories'])
            ]

        # 识别显著模式（p_value可能为NULL）
        df_significant = df[df['p_value'].notna() & (df['p_value'] < params['alpha'])]
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
            params: 网络构建参数

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

        # 从semantic_bigrams读取边（使用PMI作为权重）
        query = """
        SELECT b.cat1, b.cat2, p.pmi as weight
        FROM semantic_bigrams b
        LEFT JOIN semantic_pmi p ON b.cat1 = p.cat1 AND b.cat2 = p.cat2
        WHERE p.pmi >= ?
        """

        df = pd.read_sql_query(query, conn, params=(params['min_edge_weight'],))
        conn.close()

        # 构建网络
        G = nx.Graph()

        for _, row in df.iterrows():
            if pd.notna(row['weight']):
                G.add_edge(row['cat1'], row['cat2'], weight=float(row['weight']))

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
        region_col = 'city' if region_level == 'city' else 'county'

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
            aggregate_dict = {
                'region_name': row[region_col],
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
