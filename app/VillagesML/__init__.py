"""
VillagesML Integration Module
广东省自然村分析系统集成模块
"""
from fastapi import FastAPI, Depends


def setup_villages_routes(app: FastAPI):
    """
    Register all VillagesML routes
    注册所有 VillagesML 路由

    All endpoints will be accessible at /api/villages/*
    所有端点将通过 /api/villages/* 访问
    """
    # Import all routers
    from .character import frequency as char_frequency
    from .character import tendency as char_tendency
    from .character import embeddings as char_embeddings
    from .character import significance as char_significance
    from .village import search as village_search
    from .village import data as village_data
    from .metadata import stats as metadata_stats
    from .semantic import category as semantic_category
    from .semantic import labels as semantic_labels
    from .semantic import composition as semantic_composition
    from .semantic import subcategories as semantic_subcategories  # NEW: Phase 17
    from .clustering import assignments as cluster_assignments
    from .spatial import hotspots as spatial_hotspots
    from .spatial import integration as spatial_integration
    from .ngrams import frequency as ngram_frequency
    from .patterns import router as patterns_router
    from .regional import aggregates_realtime as regional_aggregates
    from .regional import similarity as regional_similarity  # NEW: Phase 15
    from .compute import clustering, semantic, features, subset
    from .admin import run_ids as admin_run_ids
    from .statistics import router as statistics_router  # NEW: Statistics endpoints
    from app.service.logging.dependencies.limiter import ApiLimiter

    # Register all routers with /api/villages prefix
    # Tags are defined here to avoid duplication (routers should not define their own tags)
    app.include_router(char_frequency.router, prefix="/api/villages", tags=["VillagesML-Character"], dependencies=[Depends(ApiLimiter)])
    app.include_router(char_tendency.router, prefix="/api/villages", tags=["VillagesML-Character"], dependencies=[Depends(ApiLimiter)])
    app.include_router(char_embeddings.router, prefix="/api/villages", tags=["VillagesML-Character"], dependencies=[Depends(ApiLimiter)])
    app.include_router(char_significance.router, prefix="/api/villages", tags=["VillagesML-Character"], dependencies=[Depends(ApiLimiter)])
    app.include_router(village_search.router, prefix="/api/villages", tags=["VillagesML-Village"], dependencies=[Depends(ApiLimiter)])
    app.include_router(village_data.router, prefix="/api/villages", tags=["VillagesML-Village"], dependencies=[Depends(ApiLimiter)])
    app.include_router(metadata_stats.router, prefix="/api/villages", tags=["VillagesML-Metadata"], dependencies=[Depends(ApiLimiter)])
    app.include_router(semantic_category.router, prefix="/api/villages", tags=["VillagesML-Semantic"], dependencies=[Depends(ApiLimiter)])
    app.include_router(semantic_labels.router, prefix="/api/villages", tags=["VillagesML-Semantic"], dependencies=[Depends(ApiLimiter)])
    app.include_router(semantic_composition.router, prefix="/api/villages", tags=["VillagesML-Semantic"], dependencies=[Depends(ApiLimiter)])
    app.include_router(semantic_subcategories.router, prefix="/api/villages", tags=["VillagesML-Semantic"], dependencies=[Depends(ApiLimiter)])  # NEW: Phase 17
    app.include_router(cluster_assignments.router, prefix="/api/villages", tags=["VillagesML-Clustering"], dependencies=[Depends(ApiLimiter)])
    app.include_router(spatial_hotspots.router, prefix="/api/villages", tags=["VillagesML-Spatial"], dependencies=[Depends(ApiLimiter)])
    app.include_router(spatial_integration.router, prefix="/api/villages", tags=["VillagesML-Spatial"], dependencies=[Depends(ApiLimiter)])  # Phase 16
    app.include_router(ngram_frequency.router, prefix="/api/villages", tags=["VillagesML-Ngrams"], dependencies=[Depends(ApiLimiter)])
    app.include_router(patterns_router, prefix="/api/villages", tags=["VillagesML-Patterns"], dependencies=[Depends(ApiLimiter)])
    app.include_router(regional_aggregates.router, prefix="/api/villages", tags=["VillagesML-Regional"], dependencies=[Depends(ApiLimiter)])
    app.include_router(regional_similarity.router, prefix="/api/villages", tags=["VillagesML-Regional"], dependencies=[Depends(ApiLimiter)])  # NEW: Phase 15
    app.include_router(clustering.router, prefix="/api/villages", tags=["VillagesML-Compute"], dependencies=[Depends(ApiLimiter)])
    app.include_router(semantic.router, prefix="/api/villages", tags=["VillagesML-Compute"], dependencies=[Depends(ApiLimiter)])
    app.include_router(features.router, prefix="/api/villages", tags=["VillagesML-Compute"], dependencies=[Depends(ApiLimiter)])
    app.include_router(subset.router, prefix="/api/villages", tags=["VillagesML-Compute"], dependencies=[Depends(ApiLimiter)])
    app.include_router(admin_run_ids.router, prefix="/api/villages/admin", tags=["VillagesML-Admin"], dependencies=[Depends(ApiLimiter)])
    app.include_router(statistics_router, prefix="/api/villages", tags=["VillagesML-Statistics"], dependencies=[Depends(ApiLimiter)])  # NEW
