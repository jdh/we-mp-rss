"""
过期缓存清理器 - 定时任务类型 skill

定时清理过期的缓存文件，释放磁盘空间。
"""

import os
import time
from typing import Optional

from skills.base import JobSkill
from core.log import logger


class StaleCacheCleaner(JobSkill):
    """过期缓存清理器"""

    def on_load(self, config: Optional[dict] = None) -> bool:
        """加载配置"""
        config = config or {}
        self.cache_dir = config.get("cache_dir", "data")
        self.max_age_hours = int(config.get("max_age_hours", 72))
        self.dry_run = config.get("dry_run", False)
        logger.info(
            f"[StaleCacheCleaner] 已加载, cache_dir={self.cache_dir}, "
            f"max_age_hours={self.max_age_hours}, dry_run={self.dry_run}"
        )
        return True

    def on_unload(self) -> bool:
        logger.info("[StaleCacheCleaner] 已卸载")
        return True

    def execute(self) -> dict:
        """执行清理任务"""
        if not os.path.isdir(self.cache_dir):
            return {
                "status": "skipped",
                "message": f"缓存目录不存在: {self.cache_dir}",
            }

        now = time.time()
        max_age_seconds = self.max_age_hours * 3600
        deleted_count = 0
        total_size_freed = 0
        scanned_count = 0

        for root, dirs, files in os.walk(self.cache_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                scanned_count += 1

                try:
                    stat = os.stat(filepath)
                    file_age = now - stat.st_mtime

                    if file_age > max_age_seconds:
                        file_size = stat.st_size
                        if not self.dry_run:
                            os.remove(filepath)
                        deleted_count += 1
                        total_size_freed += file_size
                except OSError as e:
                    logger.warning(f"[StaleCacheCleaner] 无法处理文件 {filepath}: {e}")

        result = {
            "status": "success",
            "message": (
                f"{'[DRY RUN] 将' if self.dry_run else '已'}清理 {deleted_count} 个过期文件，"
                f"释放 {self._format_size(total_size_freed)}，"
                f"共扫描 {scanned_count} 个文件"
            ),
            "deleted_count": deleted_count,
            "total_size_freed": total_size_freed,
            "scanned_count": scanned_count,
            "dry_run": self.dry_run,
        }

        logger.info(f"[StaleCacheCleaner] {result['message']}")
        return result

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
