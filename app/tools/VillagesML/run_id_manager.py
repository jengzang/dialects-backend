"""
Run_ID 管理器 - 从数据库动态加载活跃 run_id

此模块提供统一的 run_id 管理接口，消除硬编码，实现数据库驱动的配置管理。
"""

import sqlite3
import time
from typing import Dict, List, Optional
from pathlib import Path


class RunIDManager:
    """Run_ID 管理器 - 从数据库动态加载活跃 run_id"""

    def __init__(self, db_path: str):
        """
        初始化 RunIDManager

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._cache: Dict[str, str] = {}  # 内存缓存: {analysis_type: run_id}
        self._load_active_run_ids()

    def _load_active_run_ids(self):
        """从数据库加载活跃 run_id 到内存缓存"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT analysis_type, run_id
                FROM active_run_ids
            """)

            rows = cursor.fetchall()
            self._cache = {row[0]: row[1] for row in rows}

            conn.close()
        except sqlite3.Error as e:
            print(f"警告: 无法加载 active_run_ids: {e}")
            self._cache = {}

    def _run_id_exists(self, analysis_type: str, run_id: str) -> bool:
        """
        验证 run_id 是否存在于对应的数据表中

        Args:
            analysis_type: 分析类型标识
            run_id: 要验证的 run_id

        Returns:
            bool: run_id 是否存在
        """
        if not run_id:
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 获取对应的表名
            cursor.execute("""
                SELECT table_name FROM active_run_ids
                WHERE analysis_type = ?
            """, (analysis_type,))

            result = cursor.fetchone()
            if not result:
                conn.close()
                return False

            table_name = result[0]

            # 检查 run_id 是否存在
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE run_id = ?
                LIMIT 1
            """, (run_id,))

            count = cursor.fetchone()[0]
            conn.close()
            return count > 0

        except sqlite3.Error:
            conn.close()
            return False

    def _get_latest_run_id(self, analysis_type: str) -> Optional[str]:
        """
        获取指定分析类型的最新 run_id（按字典序）

        Args:
            analysis_type: 分析类型标识

        Returns:
            最新的 run_id，如果不存在则返回 None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 获取对应的表名
            cursor.execute("""
                SELECT table_name FROM active_run_ids
                WHERE analysis_type = ?
            """, (analysis_type,))

            result = cursor.fetchone()
            if not result:
                conn.close()
                return None

            table_name = result[0]

            # 获取最新的 run_id（按字典序降序）
            cursor.execute(f"""
                SELECT DISTINCT run_id
                FROM {table_name}
                ORDER BY run_id DESC
                LIMIT 1
            """)

            result = cursor.fetchone()
            conn.close()

            return result[0] if result else None

        except sqlite3.Error:
            conn.close()
            return None

    def get_active_run_id(self, analysis_type: str) -> str:
        """
        获取指定分析类型的活跃 run_id（带智能回退）

        如果配置的 run_id 不存在，自动使用最新的 run_id。

        Args:
            analysis_type: 分析类型标识

        Returns:
            活跃的 run_id

        Raises:
            ValueError: 如果分析类型不存在或没有可用的 run_id
        """
        if analysis_type not in self._cache:
            raise ValueError(
                f"未找到分析类型 '{analysis_type}' 的活跃 run_id。"
                f"可用类型: {list(self._cache.keys())}"
            )

        configured_run_id = self._cache[analysis_type]

        # 验证配置的 run_id 是否存在
        if self._run_id_exists(analysis_type, configured_run_id):
            return configured_run_id

        # 智能回退：使用最新的 run_id
        print(f"警告: 配置的 run_id '{configured_run_id}' 不存在，尝试使用最新版本...")
        latest_run_id = self._get_latest_run_id(analysis_type)

        if latest_run_id:
            print(f"使用最新 run_id: {latest_run_id}")
            # 自动更新缓存（但不更新数据库）
            self._cache[analysis_type] = latest_run_id
            return latest_run_id

        raise ValueError(
            f"分析类型 '{analysis_type}' 没有可用的 run_id。"
            f"请运行相应的分析脚本生成数据。"
        )

    def list_available_run_ids(self, analysis_type: str) -> List[Dict]:
        """
        列出指定分析类型的所有可用 run_id

        Args:
            analysis_type: 分析类型标识

        Returns:
            可用 run_id 列表，每个元素包含 run_id 和元数据
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取对应的表名
        cursor.execute("""
            SELECT table_name FROM active_run_ids
            WHERE analysis_type = ?
        """, (analysis_type,))

        result = cursor.fetchone()
        if not result:
            conn.close()
            return []

        table_name = result[0]

        # 查询该表中所有不同的 run_id
        try:
            cursor.execute(f"""
                SELECT DISTINCT run_id
                FROM {table_name}
                ORDER BY run_id DESC
            """)

            run_ids = [{"run_id": row[0]} for row in cursor.fetchall()]
        except sqlite3.Error:
            run_ids = []

        conn.close()
        return run_ids

    def set_active_run_id(
        self,
        analysis_type: str,
        run_id: str,
        updated_by: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """
        设置活跃 run_id（需要验证 run_id 存在）

        Args:
            analysis_type: 分析类型标识
            run_id: 新的 run_id
            updated_by: 更新者（用户/脚本名）
            notes: 备注说明

        Raises:
            ValueError: 如果 run_id 不存在或分析类型无效
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 验证分析类型存在
        cursor.execute("""
            SELECT table_name FROM active_run_ids
            WHERE analysis_type = ?
        """, (analysis_type,))

        result = cursor.fetchone()
        if not result:
            conn.close()
            raise ValueError(f"未找到分析类型: {analysis_type}")

        table_name = result[0]

        # 验证 run_id 存在于对应的表中
        try:
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE run_id = ?
            """, (run_id,))

            count = cursor.fetchone()[0]
            if count == 0:
                conn.close()
                raise ValueError(
                    f"run_id '{run_id}' 在表 '{table_name}' 中不存在"
                )
        except sqlite3.Error as e:
            conn.close()
            raise ValueError(f"验证 run_id 失败: {e}")

        # 更新活跃 run_id
        cursor.execute("""
            UPDATE active_run_ids
            SET run_id = ?, updated_at = ?, updated_by = ?, notes = ?
            WHERE analysis_type = ?
        """, (run_id, time.time(), updated_by, notes, analysis_type))

        conn.commit()
        conn.close()

        # 更新缓存
        self._cache[analysis_type] = run_id

    def get_run_id_metadata(self, run_id: str) -> Dict:
        """
        获取 run_id 的元数据（从 analysis_runs/embedding_runs 等表）

        Args:
            run_id: run_id 标识

        Returns:
            元数据字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metadata = {"run_id": run_id, "found": False}

        # 尝试从 analysis_runs 表查询
        try:
            cursor.execute("""
                SELECT created_at, status, total_villages, total_chars
                FROM analysis_runs
                WHERE run_id = ?
            """, (run_id,))

            result = cursor.fetchone()
            if result:
                metadata.update({
                    "found": True,
                    "source": "analysis_runs",
                    "created_at": result[0],
                    "status": result[1],
                    "total_villages": result[2],
                    "total_chars": result[3]
                })
                conn.close()
                return metadata
        except sqlite3.Error:
            pass

        # 尝试从 embedding_runs 表查询
        try:
            cursor.execute("""
                SELECT created_at, vector_size, window_size, min_count
                FROM embedding_runs
                WHERE run_id = ?
            """, (run_id,))

            result = cursor.fetchone()
            if result:
                metadata.update({
                    "found": True,
                    "source": "embedding_runs",
                    "created_at": result[0],
                    "vector_size": result[1],
                    "window_size": result[2],
                    "min_count": result[3]
                })
        except sqlite3.Error:
            pass

        conn.close()
        return metadata

    def auto_update_from_script(
        self,
        analysis_type: str,
        run_id: str,
        script_name: str,
        notes: Optional[str] = None
    ):
        """
        从分析脚本自动更新活跃 run_id

        此方法专门用于分析脚本在完成后自动更新 active_run_ids 表。
        与 set_active_run_id 不同，此方法不验证 run_id 是否存在（因为数据可能刚写入）。

        Args:
            analysis_type: 分析类型标识
            run_id: 新的 run_id
            script_name: 脚本名称（用于追踪）
            notes: 备注说明（可选）

        Example:
            >>> manager = RunIDManager("data/villages.db")
            >>> manager.auto_update_from_script(
            ...     "spatial_hotspots",
            ...     "final_04_20260222_150000",
            ...     "phase_04_spatial_analysis",
            ...     "空间分析完成，发现8个热点"
            ... )
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 检查分析类型是否存在
        cursor.execute("""
            SELECT table_name FROM active_run_ids
            WHERE analysis_type = ?
        """, (analysis_type,))

        result = cursor.fetchone()
        if not result:
            conn.close()
            print(f"警告: 分析类型 '{analysis_type}' 不存在于 active_run_ids 表中")
            return

        # 更新活跃 run_id（不验证是否存在）
        cursor.execute("""
            UPDATE active_run_ids
            SET run_id = ?, updated_at = ?, updated_by = ?, notes = ?
            WHERE analysis_type = ?
        """, (run_id, time.time(), script_name, notes, analysis_type))

        conn.commit()
        conn.close()

        # 更新缓存
        self._cache[analysis_type] = run_id

        print(f"✓ 已自动更新 {analysis_type} 的活跃 run_id 为: {run_id}")

    def refresh_cache(self):
        """刷新内存缓存"""
        self._load_active_run_ids()

    def get_all_active_run_ids(self) -> Dict[str, Dict]:
        """
        获取所有分析类型的活跃 run_id

        Returns:
            字典，键为 analysis_type，值为包含 run_id 和元数据的字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT analysis_type, run_id, table_name, updated_at, updated_by, notes
            FROM active_run_ids
            ORDER BY analysis_type
        """)

        rows = cursor.fetchall()
        result = {}

        for row in rows:
            result[row[0]] = {
                "run_id": row[1],
                "table_name": row[2],
                "updated_at": row[3],
                "updated_by": row[4],
                "notes": row[5]
            }

        conn.close()
        return result


# 全局单例实例
_manager_instance: Optional[RunIDManager] = None


def get_run_id_manager(db_path: str = "data/villages.db") -> RunIDManager:
    """
    获取 RunIDManager 单例实例

    Args:
        db_path: 数据库路径

    Returns:
        RunIDManager 实例
    """
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = RunIDManager(db_path)

    return _manager_instance


# 导出便捷访问的全局实例
run_id_manager = get_run_id_manager()
