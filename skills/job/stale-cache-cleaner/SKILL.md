---
name: stale-cache-cleaner
description: 定时清理过期的视图缓存文件。当系统运行一段时间后缓存目录膨胀时自动清理，释放磁盘空间。
version: 1.0.0
type: job
trigger: "0 3 * * *"
dependencies: []
---

# 过期缓存清理器

## 功能
定时清理 `data/` 目录下的过期缓存文件，防止磁盘占用过大。

## 配置项
- `cache_dir`: 缓存目录路径（默认 "data"）
- `max_age_hours`: 文件最大保留时间，小时（默认 72）
- `dry_run`: 仅报告不实际删除（默认 false）
