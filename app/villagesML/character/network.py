"""
字符网络 API
Character Network API endpoint — BFS expansion over character similarity graph
"""
from collections import defaultdict

from fastapi import APIRouter, Depends
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query
from ..run_id_manager import get_run_id_manager
from ..schema_runtime import qcolumn, qtable, run_id_analysis_type
from ..schema_keys import C, T
from ..models import (
    CharacterNetworkRequest,
    CharacterNetworkResponse,
    NetworkNode,
    CharacterNetworkEdge,
)

router = APIRouter(prefix="/character")


@router.post("/network", response_model=CharacterNetworkResponse)
def get_character_network(
    req: CharacterNetworkRequest,
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """BFS 扩展字符相似性网络，返回完整图数据（节点 + 边）。"""
    table = qtable(dbpath, T.CHAR_SIMILARITY)
    run_id_col = qcolumn(dbpath, T.CHAR_SIMILARITY, C.CHAR_SIMILARITY.RUN_ID)
    char1_col = qcolumn(dbpath, T.CHAR_SIMILARITY, C.CHAR_SIMILARITY.CHAR1)
    char2_col = qcolumn(dbpath, T.CHAR_SIMILARITY, C.CHAR_SIMILARITY.CHAR2)
    similarity_col = qcolumn(dbpath, T.CHAR_SIMILARITY, C.CHAR_SIMILARITY.COSINE_SIMILARITY)

    run_id = get_run_id_manager(dbpath).get_active_run_id(
        run_id_analysis_type(dbpath, T.CHAR_SIMILARITY)
    )

    visited: dict[str, tuple[int, float]] = {req.root_char: (0, 1.0)}
    edges: dict[frozenset, float] = {}
    frontier = [req.root_char]

    for depth in range(req.depth):
        if not frontier or len(visited) >= req.max_nodes:
            break

        placeholders = ",".join(["?"] * len(frontier))
        query = f"""
            SELECT {char1_col} as source, {char2_col} as target, {similarity_col} as similarity
            FROM {table}
            WHERE {run_id_col} = ? AND {char1_col} IN ({placeholders})
              AND {similarity_col} >= ?
            ORDER BY {similarity_col} DESC
        """
        results = execute_query(db, query, (run_id, *frontier, req.min_similarity))

        by_source = defaultdict(list)
        for row in results:
            if len(by_source[row["source"]]) < req.top_k:
                by_source[row["source"]].append(row)

        next_frontier = []
        for source, sims in by_source.items():
            for row in sims:
                target = row["target"]
                sim = row["similarity"]
                edge_key = frozenset((source, target))
                if edge_key not in edges or edges[edge_key] < sim:
                    edges[edge_key] = sim
                if target not in visited:
                    if len(visited) >= req.max_nodes:
                        break
                    visited[target] = (depth + 1, sim)
                    next_frontier.append(target)

        frontier = next_frontier

    nodes = [
        NetworkNode(character=char, depth=d, similarity=s)
        for char, (d, s) in visited.items()
    ]
    edges_resp = [
        CharacterNetworkEdge(source=s, target=t, similarity=sim)
        for (s, t), sim in edges.items()
    ]

    return CharacterNetworkResponse(nodes=nodes, edges=edges_resp)
