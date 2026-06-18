"""
Skill 系统入口

使用方式：
    from skills import SkillRegistry

    # 启动时
    SkillRegistry.discover()
    SkillRegistry.load_enabled(cfg.get("skills", {}))

    # 获取过滤器
    filters = SkillRegistry.get_filters("article.before_save")

    # 获取定时任务
    jobs = SkillRegistry.get_jobs()
"""

from skills.registry import SkillRegistry

__all__ = ["SkillRegistry"]
