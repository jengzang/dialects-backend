"""
Batch Vector Operations - 批量向量操作端点
"""

# 这些代码应该添加到 aggregates_realtime.py 文件末尾

# ============================================================================
# Batch Vector Operations API
# ============================================================================

from .batch_vector_models import (
    RegionSpec, BatchCompareRequest, BatchCompareResponse,
    ReduceRequest, ReduceResponse,
    ClusterRequest, ClusterResponse
)


def get_multiple_vectors(
    db: sqlite3.Connection,
    regions: List[RegionSpec],
    run_id: str
) -> tuple[np.ndarray, List[Dict[str, Any]], List[str]]:
    """
    获取多个区域的向量

    Args:
        db: 数据库连接
        regions: 区域规格列表
        run_id: 分析运行ID

    Returns:
        (向量矩阵, 区域信息列表, 类别列表)
    """
    vectors = []
    region_infos = []
    categories = None

    for region_spec in regions:
        vector, cats, region_name, hierarchy = get_semantic_vector_by_hierarchy(
            db,
            region_spec.level,
            region_spec.city,
            region_spec.county,
            region_spec.township,
            run_id
        )

        vectors.append(vector)
        region_infos.append({
            'region_name': region_name,
            'level': region_spec.level,
            'city': hierarchy.get('city'),
            'county': hierarchy.get('county'),
            'township': hierarchy.get('township')
        })

        if categories is None:
            categories = cats

    return np.array(vectors), region_infos, categories


@router.post("/vectors/compare/batch", response_model=BatchCompareResponse)
def batch_compare_vectors(
    request: BatchCompareRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    批量比较多个区域的向量，返回相似度矩阵
    Batch compare multiple region vectors, returns similarity matrix

    用于热力图可视化。
    Used for heatmap visualization.

    Args:
        request: 批量比较请求参数
        db: 数据库连接

    Returns:
        BatchCompareResponse: 包含相似度矩阵和距离矩阵

    Example:
        {
            "regions": [
                {"level": "city", "city": "广州市"},
                {"level": "city", "city": "深圳市"},
                {"level": "city", "city": "佛山市"}
            ]
        }
    """
    if len(request.regions) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 regions are required for batch comparison"
        )

    if len(request.regions) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum 100 regions allowed for batch comparison"
        )

    # 获取 run_id
    if request.run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")
    else:
        run_id = request.run_id

    # 获取所有区域的向量
    vectors, region_infos, categories = get_multiple_vectors(db, request.regions, run_id)

    n = len(vectors)

    # 计算相似度矩阵（余弦相似度）
    similarity_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                similarity_matrix[i][j] = 1.0
            elif i < j:
                sim = 1 - cosine(vectors[i], vectors[j])
                similarity_matrix[i][j] = sim
                similarity_matrix[j][i] = sim

    # 计算距离矩阵（欧氏距离）
    distance_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i < j:
                dist = euclidean(vectors[i], vectors[j])
                distance_matrix[i][j] = dist
                distance_matrix[j][i] = dist

    return BatchCompareResponse(
        regions=region_infos,
        similarity_matrix=[[round(v, 6) for v in row] for row in similarity_matrix.tolist()],
        distance_matrix=[[round(v, 6) for v in row] for row in distance_matrix.tolist()],
        feature_dimension=9,
        categories=categories,
        run_id=run_id
    )


@router.post("/vectors/reduce", response_model=ReduceResponse)
def reduce_vectors(
    request: ReduceRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    向量降维（PCA 或 t-SNE）
    Dimensionality reduction (PCA or t-SNE)

    用于散点图可视化。
    Used for scatter plot visualization.

    Args:
        request: 降维请求参数
        db: 数据库连接

    Returns:
        ReduceResponse: 包含降维后的坐标

    Example:
        {
            "regions": [
                {"level": "city", "city": "广州市"},
                {"level": "city", "city": "深圳市"},
                {"level": "city", "city": "佛山市"}
            ],
            "method": "pca",
            "n_components": 2
        }
    """
    if len(request.regions) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 regions are required for dimensionality reduction"
        )

    if request.n_components not in [2, 3]:
        raise HTTPException(
            status_code=400,
            detail="n_components must be 2 or 3"
        )

    if request.method not in ["pca", "tsne"]:
        raise HTTPException(
            status_code=400,
            detail="method must be 'pca' or 'tsne'"
        )

    # 获取 run_id
    if request.run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")
    else:
        run_id = request.run_id

    # 获取所有区域的向量
    vectors, region_infos, categories = get_multiple_vectors(db, request.regions, run_id)

    # 标准化
    scaler = StandardScaler()
    vectors_scaled = scaler.fit_transform(vectors)

    # 降维
    explained_variance = None
    if request.method == "pca":
        reducer = PCA(n_components=request.n_components)
        coordinates = reducer.fit_transform(vectors_scaled)
        explained_variance = reducer.explained_variance_ratio_.tolist()
    else:  # tsne
        # t-SNE 需要至少 n_components + 1 个样本
        if len(vectors) < request.n_components + 1:
            raise HTTPException(
                status_code=400,
                detail=f"t-SNE requires at least {request.n_components + 1} regions"
            )
        reducer = TSNE(n_components=request.n_components, random_state=42)
        coordinates = reducer.fit_transform(vectors_scaled)

    return ReduceResponse(
        regions=region_infos,
        coordinates=[[round(v, 6) for v in row] for row in coordinates.tolist()],
        method=request.method,
        n_components=request.n_components,
        explained_variance=[round(v, 6) for v in explained_variance] if explained_variance else None,
        run_id=run_id
    )


@router.post("/vectors/cluster", response_model=ClusterResponse)
def cluster_vectors(
    request: ClusterRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    向量聚类（KMeans、DBSCAN 或 GMM）
    Vector clustering (KMeans, DBSCAN, or GMM)

    发现语义相似的区域群组。
    Discover semantically similar region groups.

    Args:
        request: 聚类请求参数
        db: 数据库连接

    Returns:
        ClusterResponse: 包含聚类标签和中心点

    Examples:
        // KMeans
        {
            "regions": [...],
            "method": "kmeans",
            "n_clusters": 3
        }

        // DBSCAN
        {
            "regions": [...],
            "method": "dbscan",
            "eps": 0.5,
            "min_samples": 2
        }

        // GMM
        {
            "regions": [...],
            "method": "gmm",
            "n_clusters": 3
        }
    """
    if len(request.regions) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 regions are required for clustering"
        )

    if request.method not in ["kmeans", "dbscan", "gmm"]:
        raise HTTPException(
            status_code=400,
            detail="method must be 'kmeans', 'dbscan', or 'gmm'"
        )

    # 验证参数
    if request.method in ["kmeans", "gmm"]:
        if request.n_clusters is None:
            raise HTTPException(
                status_code=400,
                detail=f"{request.method} requires n_clusters parameter"
            )
        if request.n_clusters < 2 or request.n_clusters > len(request.regions):
            raise HTTPException(
                status_code=400,
                detail=f"n_clusters must be between 2 and {len(request.regions)}"
            )

    if request.method == "dbscan":
        if request.eps is None or request.min_samples is None:
            raise HTTPException(
                status_code=400,
                detail="dbscan requires eps and min_samples parameters"
            )

    # 获取 run_id
    if request.run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")
    else:
        run_id = request.run_id

    # 获取所有区域的向量
    vectors, region_infos, categories = get_multiple_vectors(db, request.regions, run_id)

    # 标准化
    scaler = StandardScaler()
    vectors_scaled = scaler.fit_transform(vectors)

    # 聚类
    cluster_centers = None
    if request.method == "kmeans":
        clusterer = KMeans(n_clusters=request.n_clusters, random_state=42)
        labels = clusterer.fit_predict(vectors_scaled)
        # 反标准化中心点
        cluster_centers = scaler.inverse_transform(clusterer.cluster_centers_)
        n_clusters = request.n_clusters

    elif request.method == "dbscan":
        clusterer = DBSCAN(eps=request.eps, min_samples=request.min_samples)
        labels = clusterer.fit_predict(vectors_scaled)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    else:  # gmm
        clusterer = GaussianMixture(n_components=request.n_clusters, random_state=42)
        labels = clusterer.fit_predict(vectors_scaled)
        # 反标准化中心点
        cluster_centers = scaler.inverse_transform(clusterer.means_)
        n_clusters = request.n_clusters

    return ClusterResponse(
        regions=region_infos,
        labels=labels.tolist(),
        n_clusters=n_clusters,
        cluster_centers=[[round(v, 6) for v in row] for row in cluster_centers.tolist()] if cluster_centers is not None else None,
        method=request.method,
        run_id=run_id
    )
