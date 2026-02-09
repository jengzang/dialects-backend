# app/tools/__init__.py
"""
工具路由模块：将check、jyut2ipa、merge三个工具的Web界面路由挂载到FastAPI app。
"""

from fastapi import FastAPI


def setup_tools_routes(app: FastAPI):
    """
    注册所有工具路由
    """
    from app.tools.check.check_routes import router as check_router
    from app.tools.jyut2ipa.jyut2ipa_routes import router as jyut2ipa_router
    from app.tools.merge.merge_routes import router as merge_router

    app.include_router(check_router, prefix="/api/tools/check", tags=["工具-Check"])
    app.include_router(jyut2ipa_router, prefix="/api/tools/jyut2ipa", tags=["工具-Jyut2IPA"])
    app.include_router(merge_router, prefix="/api/tools/merge", tags=["工具-Merge"])
