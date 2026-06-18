---
name: content-sanitizer
description: 清洗文章内容，移除常见广告和无关元素。当文章内容包含第三方广告、空链接或无关 div 时自动清理。
version: 1.0.0
type: filter
pipeline: article.before_save
priority: 10
dependencies: []
---

# 内容清洗器

## 功能
清洗文章 HTML 内容，移除：
- 常见广告 class/id 的 div 元素
- 空的 `<a>` 标签（无 href 或空 href）
- 仅包含空白的 `<p>` 标签

## 配置项
- `remove_empty_links`: 是否移除空链接（默认 true）
- `remove_empty_paragraphs`: 是否移除空段落（默认 true）
