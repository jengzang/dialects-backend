"""
语义分析API (Semantic Analysis API)

提供语义共现和网络分析接口：
- POST /api/compute/semantic/cooccurrence - 共现分析
- POST /api/compute/semantic/network - 网络构建
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

from .validators import SemanticAnalysisParams, SemanticNetworkParams
from .cache import compute_cache
from .engine import SemanticEngine
from ..config import get_db_path

# 导入身份验证依赖

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compute/semantic")


def get_semantic_engine():
    """获取语义引擎实例"""
    db_path = get_db_path()
    return SemanticEngine(db_path)


@router.post("/cooccurrence")
async def analyze_cooccurrence(
    params: SemanticAnalysisParams,  # 添加身份验证
    engine: SemanticEngine = Depends(get_semantic_engine)
) -> Dict[str, Any]:
    """
    分析语义共现（需要登录）

    Args:
        params: 分析参数
        user: 当前用户（由 ApiLimiter 自动验证）

    Returns:
        共现分析结果

    Raises:
        HTTPException: 如果未登录、分析失败或超时
    """
    # 检查用户是否登录
    if not user:
        raise HTTPException(status_code=401, detail="此功能需要登录")

    try:
        # 检查缓存
        cached_result = compute_cache.get("semantic_cooccurrence", params.dict())
        if cached_result:
            logger.info("Returning cached cooccurrence result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Analyzing cooccurrence: region={params.region_name}, level={params.region_level}")

        # 执行分析
        result = engine.analyze_cooccurrence(params.dict())

        # 缓存结果
        compute_cache.set("semantic_cooccurrence", params.dict(), result)

        result['from_cache'] = False
        return result

    except Exception as e:
        logger.error(f"Cooccurrence analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/network")
async def build_semantic_network(
    params: SemanticNetworkParams,  # 添加身份验证
    engine: SemanticEngine = Depends(get_semantic_engine)
) -> Dict[str, Any]:
    """
    构建语义网络（需要登录）

    Args:
        params: 网络参数
        user: 当前用户（由 ApiLimiter 自动验证）

    Returns:
        语义网络结果

    Raises:
        HTTPException: 如果未登录、构建失败或超时
    """
    # 检查用户是否登录
    if not user:
        raise HTTPException(status_code=401, detail="此功能需要登录")

    try:
        # 检查缓存
        cached_result = compute_cache.get("semantic_network", params.dict())
        if cached_result:
            logger.info("Returning cached network result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Building semantic network: region={params.region_name}")

        # 构建网络
        result = engine.build_semantic_network(params.dict())

        # 缓存结果
        compute_cache.set("semantic_network", params.dict(), result)

        result['from_cache'] = False
        return result

    except Exception as e:
        logger.error(f"Network building error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Network building failed: {str(e)}")


