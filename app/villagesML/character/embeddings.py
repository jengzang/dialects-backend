"""
字符嵌入API
Character Embeddings API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3
import json

from ..dependencies import get_db, execute_query, execute_single

router = APIRouter(prefix="/character/embeddings")

# 向量维度常量
VECTOR_DIM = 225

# 使用最终版本的嵌入
ACTIVE_RUN_ID = "embed_final_001"


@router.get("/vector")
def get_character_embedding(
    char: str = Query(..., description="字符", min_length=1, max_length=1),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取字符的Word2Vec嵌入向量
    Get Word2Vec embedding vector for a character

    Args:
        char: 字符

    Returns:
        dict: 字符嵌入信息（包含向量）
    """
    query = """
        SELECT
            char as character,
            embedding_vector
        FROM char_embeddings
        WHERE run_id = ? AND char = ?
    """

    result = execute_single(db, query, (ACTIVE_RUN_ID, char))

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
    top_k: int = Query(10, ge=1, le=50, description="返回前K个相似字符"),
    min_similarity: Optional[float] = Query(None, ge=0.0, le=1.0, description="最小相似度阈值"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取与指定字符最相似的字符
    Get most similar characters to a given character

    Args:
        char: 字符
        top_k: 返回前K个相似字符
        min_similarity: 最小相似度阈值（可选）

    Returns:
        dict: 包含查询信息和相似字符列表
    """
    query = """
        SELECT
            char2 as character,
            cosine_similarity as similarity
        FROM char_similarity
        WHERE run_id = ? AND char1 = ?
    """
    params = [ACTIVE_RUN_ID, char]

    # 现场过滤：最小相似度
    if min_similarity is not None:
        query += " AND cosine_similarity >= ?"
        params.append(min_similarity)

    query += " ORDER BY cosine_similarity DESC LIMIT ?"
    params.append(top_k)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No similarities found for character: {char}"
        )

    return {
        "query_character": char,
        "top_k": top_k,
        "similarities": results
    }


@router.get("/list")
def list_character_embeddings(
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    列出所有字符嵌入（不包含向量，仅元数据）
    List all character embeddings (metadata only, no vectors)

    Args:
        limit: 返回记录数
        offset: 偏移量

    Returns:
        dict: 包含分页信息和字符嵌入元数据列表
    """
    # 获取总数
    count_query = "SELECT COUNT(*) as total FROM char_embeddings WHERE run_id = ?"
    count_result = execute_single(db, count_query, (ACTIVE_RUN_ID,))
    total = count_result["total"] if count_result else 0

    # 获取数据
    query = """
        SELECT
            char as character,
            char_frequency as frequency
        FROM char_embeddings
        WHERE run_id = ?
        ORDER BY char
        LIMIT ? OFFSET ?
    """

    results = execute_query(db, query, (ACTIVE_RUN_ID, limit, offset))

    # 添加 vector_dim 信息
    embeddings = [
        {
            **item,
            "vector_dim": VECTOR_DIM
        }
        for item in results
    ]

    return {
        "embeddings": embeddings,
        "total": total,
        "limit": limit,
        "offset": offset,
        "page": (offset // limit) + 1,
        "page_size": limit
    }
