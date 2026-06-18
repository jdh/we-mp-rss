"""
内容清洗器 - 管道/过滤器类型 skill

在文章保存前清洗 HTML 内容，移除广告和无关元素。
"""

import re
from typing import Optional

from skills.base import FilterSkill
from core.log import logger


class ContentSanitizer(FilterSkill):
    """内容清洗器"""

    def on_load(self, config: Optional[dict] = None) -> bool:
        """加载配置"""
        config = config or {}
        self.remove_empty_links = config.get("remove_empty_links", True)
        self.remove_empty_paragraphs = config.get("remove_empty_paragraphs", True)
        logger.info(f"[ContentSanitizer] 已加载, remove_empty_links={self.remove_empty_links}, remove_empty_paragraphs={self.remove_empty_paragraphs}")
        return True

    def on_unload(self) -> bool:
        logger.info("[ContentSanitizer] 已卸载")
        return True

    def process(self, data: dict) -> dict:
        """
        清洗文章内容。

        支持的 data 字段：
        - content: HTML 内容字符串
        - title: 文章标题（可选，不做处理）
        """
        content = data.get("content", "")
        if not content:
            return data

        original_length = len(content)

        # 移除常见广告 div
        content = self._remove_ad_divs(content)

        # 移除空链接
        if self.remove_empty_links:
            content = self._remove_empty_links(content)

        # 移除空段落
        if self.remove_empty_paragraphs:
            content = self._remove_empty_paragraphs(content)

        new_length = len(content)
        if original_length != new_length:
            logger.info(
                f"[ContentSanitizer] 文章已清洗: "
                f"原始 {original_length} 字符 -> {new_length} 字符 "
                f"({((original_length - new_length) / max(original_length, 1)) * 100:.1f}% 减少)"
            )

        data["content"] = content
        return data

    # ---- 内部清洗方法 ----

    _AD_CLASS_PATTERNS = [
        r'<div[^>]*class="[^"]*ad[^"]*"[^>]*>.*?</div>',
        r'<div[^>]*id="[^"]*ad[^"]*"[^>]*>.*?</div>',
        r'<div[^>]*class="[^"]*advertisement[^"]*"[^>]*>.*?</div>',
    ]

    def _remove_ad_divs(self, html: str) -> str:
        """移除包含广告 class/id 的 div"""
        for pattern in self._AD_CLASS_PATTERNS:
            html = re.sub(pattern, "", html, flags=re.IGNORECASE | re.DOTALL)
        return html

    @staticmethod
    def _remove_empty_links(html: str) -> str:
        """移除空的 a 标签（无 href 或 href 为空）"""
        return re.sub(
            r'<a(?:\s+[^>]*)?\s+href=["\'\s]*["\'\s]?[^>]*>.*?</a>',
            "",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    @staticmethod
    def _remove_empty_paragraphs(html: str) -> str:
        """移除仅包含空白的 p 标签"""
        return re.sub(
            r'<p[^>]*>\s*</p>',
            "",
            html,
            flags=re.IGNORECASE,
        )
