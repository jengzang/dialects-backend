# app/tools/__init__.py
"""
工具路由模块：将所有工具模块统一挂载到 FastAPI app。
"""

from fastapi import FastAPI, Depends


def setup_tools_routes(app: FastAPI):
    """
    注册所有工具路由
    """
    from app.tools.check.check_routes import router as check_router
    from app.tools.cluster.routes import router as cluster_router
    from app.tools.jyut2ipa.jyut2ipa_routes import router as jyut2ipa_router
    from app.tools.merge.merge_routes import router as merge_router
    from app.tools.praat.routes import router as praat_router
    from app.service.logging.dependencies.limiter import ApiLimiter

    app.include_router(check_router, prefix="/api/tools/check", tags=["工具-Check"], dependencies=[Depends(ApiLimiter)])
    app.include_router(cluster_router, prefix="/api/tools/cluster", tags=["工具-Cluster"], dependencies=[Depends(ApiLimiter)])
    app.include_router(jyut2ipa_router, prefix="/api/tools/jyut2ipa", tags=["工具-Jyut2IPA"], dependencies=[Depends(ApiLimiter)])
    app.include_router(merge_router, prefix="/api/tools/merge", tags=["工具-Merge"], dependencies=[Depends(ApiLimiter)])
    app.include_router(praat_router, prefix="/api/tools/praat", tags=["工具-Praat"], dependencies=[Depends(ApiLimiter)])
