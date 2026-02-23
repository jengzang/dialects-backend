"""
字符嵌入API
Character Embeddings API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3
import json

from ..dependencies import get_db, execute_query, execute_single
from ..config import DEFAULT_RUN_ID
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/character/embeddings", tags=["character"])


@router.get("/vector")
def get_character_embedding(
    char: str = Query(..., description="字符", min_length=1, max_length=1),
    run_id: Optional[str] = Query(None, description="嵌入运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取字符的Word2Vec嵌入向量
    Get Word2Vec embedding vector for a character

    Args:
        char: 字符
        run_id: 嵌入运行ID

    Returns:
        dict: 字符嵌入信息（包含向量）
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("char_embeddings")

    query = """
        SELECT
            char as character,
            embedding_vector
        FROM char_embeddings
        WHERE run_id = ? AND char = ?
    """

    result = execute_single(db, query, (run_id, char))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No embedding found for character: {char}"
        )

    # 解析嵌入向量（如果存储为JSON字符串）
    if isinstance(result.get("embedding_vector"), str):
        result["embedding_vector"] = json.loads(result["embedding_vector"])

    return result


@router.get("/similarities")
def get_similar_characters(
    char: str = Query(..., description="字符", min_length=1, max_length=1),
    run_id: Optional[str] = Query(None, description="嵌入运行ID（留空使用活跃版本）"),
    top_k: int = Query(10, ge=1, le=50, description="返回前K个相似字符"),
    min_similarity: Optional[float] = Query(None, ge=0.0, le=1.0, description="最小相似度阈值"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取与指定字符最相似的字符
    Get most similar characters to a given character

    Args:
        char: 字符
        run_id: 嵌入运行ID
        top_k: 返回前K个相似字符
        min_similarity: 最小相似度阈值（可选）

    Returns:
        List[dict]: 相似字符列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("char_embeddings")

    query = """
        SELECT
            char2 as similar_character,
            cosine_similarity as similarity
        FROM char_similarity
        WHERE run_id = ? AND char1 = ?
    """
    params = [run_id, char]

    # 现场过滤：最小相似度
    if min_similarity is not None:
        query += " AND similarity >= ?"
        params.append(min_similarity)

    query += " ORDER BY similarity DESC LIMIT ?"
    params.append(top_k)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No similarities found for character: {char}"
        )

    return results


@router.get("/list")
def list_character_embeddings(
    run_id: Optional[str] = Query(None, description="嵌入运行ID（留空使用活跃版本）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    列出所有字符嵌入（不包含向量，仅元数据）
    List all character embeddings (metadata only, no vectors)

    Args:
        run_id: 嵌入运行ID
        limit: 返回记录数
        offset: 偏移量

    Returns:
        List[dict]: 字符嵌入元数据列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("char_embeddings")

    query = """
        SELECT
            char as character
        FROM char_embeddings
        WHERE run_id = ?
        ORDER BY char
        LIMIT ? OFFSET ?
    """

    results = execute_query(db, query, (run_id, limit, offset))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No embeddings found for run_id: {run_id}"
        )

    return results
