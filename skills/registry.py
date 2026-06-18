"""
Skill 注册表

负责 skill 的发现、加载、生命周期管理。
参考三层渐进式披露模式：
- discover(): 第一级，只解析 SKILL.md frontmatter
- load_enabled(): 第二级，import 代码模块并调用 on_load
- 第三级资源按需加载（暂未实现）
"""

import os
import importlib
import yaml
from typing import Optional

from core.log import logger
from core.print import print_info, print_warning, print_error
from skills.base import BaseSkill, FilterSkill, JobSkill


class SkillRegistry:
    """单例注册表"""

    _skills: dict[str, BaseSkill] = {}  # name -> skill 实例
    _loaded: bool = False
    _skills_dir: str = ""

    @classmethod
    def discover(cls, skills_dir: str = "skills") -> list[dict]:
        """
        第一级加载：扫描 skills 目录，只解析 SKILL.md 的 YAML frontmatter。

        Args:
            skills_dir: skill 根目录路径

        Returns:
            发现的所有 skill 元数据列表
        """
        cls._skills_dir = skills_dir
        discovered = []

        for skill_type in ("filter", "job"):
            type_dir = os.path.join(skills_dir, skill_type)
            if not os.path.isdir(type_dir):
                continue

            for entry in os.listdir(type_dir):
                skill_dir = os.path.join(type_dir, entry)
                skill_md = os.path.join(skill_dir, "SKILL.md")

                if not os.path.isdir(skill_dir) or not os.path.isfile(skill_md):
                    continue

                try:
                    metadata = cls._parse_frontmatter(skill_md)
                    if not metadata:
                        continue

                    metadata["_skill_dir"] = skill_dir
                    metadata["_skill_type"] = skill_type
                    discovered.append(metadata)
                    print_info(f"[Skill] 发现: {metadata.get('name')} ({skill_type})")

                except Exception as e:
                    print_warning(f"[Skill] 解析失败 {skill_dir}: {e}")

        print_info(f"[Skill] 共发现 {len(discovered)} 个 skill")
        return discovered

    @classmethod
    def load_enabled(cls, config: Optional[dict] = None) -> int:
        """
        第二级加载：根据 config.yaml 的 skills 段加载启用的 skill。

        Args:
            config: config.yaml 中 skills 段的配置字典

        Returns:
            成功加载的 skill 数量
        """
        if config is None:
            config = {}

        loaded_count = 0

        for skill_type in ("filter", "job"):
            type_dir = os.path.join(cls._skills_dir, skill_type)
            if not os.path.isdir(type_dir):
                continue

            for entry in os.listdir(type_dir):
                skill_dir = os.path.join(type_dir, entry)
                skill_md = os.path.join(skill_dir, "SKILL.md")

                if not os.path.isdir(skill_dir) or not os.path.isfile(skill_md):
                    continue

                metadata = cls._parse_frontmatter(skill_md)
                if not metadata:
                    continue

                name = metadata.get("name", "")
                skill_config = config.get(name, {})
                enabled = skill_config.get("enabled", False)

                if not enabled:
                    continue

                try:
                    skill = cls._load_skill(skill_dir, skill_type, metadata, skill_config)
                    if skill:
                        cls._skills[name] = skill
                        loaded_count += 1
                        print_info(f"[Skill] 已加载: {name} v{skill.version}")
                except Exception as e:
                    print_error(f"[Skill] 加载失败 {name}: {e}")

        cls._loaded = True
        print_info(f"[Skill] 共加载 {loaded_count} 个 skill")
        return loaded_count

    @classmethod
    def get_filters(cls, pipeline: str) -> list:
        """
        获取指定管道的过滤器列表，按 priority 排序。

        Args:
            pipeline: 管道阶段名称

        Returns:
            排序后的 FilterSkill 列表
        """
        filters = [
            s for s in cls._skills.values()
            if isinstance(s, FilterSkill) and s.pipeline == pipeline and s.enabled
        ]
        filters.sort(key=lambda x: x.priority)
        return filters

    @classmethod
    def get_jobs(cls) -> list:
        """
        获取所有已加载的定时任务 skill。

        Returns:
            JobSkill 列表
        """
        return [
            s for s in cls._skills.values()
            if isinstance(s, JobSkill) and s.enabled
        ]

    @classmethod
    def get(cls, name: str) -> Optional[BaseSkill]:
        """根据名称获取 skill"""
        return cls._skills.get(name)

    @classmethod
    def list_all(cls) -> list[dict]:
        """列出所有 skill 及其状态"""
        result = []
        # 先列出已加载的
        for name, skill in cls._skills.items():
            result.append({
                "name": name,
                "description": skill.description,
                "version": skill.version,
                "type": skill.skill_type,
                "enabled": skill.enabled,
                "loaded": True,
            })

        # 再列出已发现但未加载的
        for skill_type in ("filter", "job"):
            type_dir = os.path.join(cls._skills_dir, skill_type)
            if not os.path.isdir(type_dir):
                continue
            for entry in os.listdir(type_dir):
                skill_dir = os.path.join(type_dir, entry)
                skill_md = os.path.join(skill_dir, "SKILL.md")
                if not os.path.isdir(skill_dir) or not os.path.isfile(skill_md):
                    continue
                metadata = cls._parse_frontmatter(skill_md)
                if not metadata:
                    continue
                name = metadata.get("name", "")
                if name not in cls._skills:
                    result.append({
                        "name": name,
                        "description": metadata.get("description", ""),
                        "version": metadata.get("version", "1.0.0"),
                        "type": metadata.get("type", skill_type),
                        "enabled": False,
                        "loaded": False,
                    })

        return result

    @classmethod
    def unload_all(cls):
        """卸载所有 skill"""
        for name, skill in list(cls._skills.items()):
            try:
                skill.on_unload()
            except Exception as e:
                print_warning(f"[Skill] 卸载 {name} 时出错: {e}")
        cls._skills.clear()
        cls._loaded = False

    # ---- 内部方法 ----

    @classmethod
    def _parse_frontmatter(cls, filepath: str) -> Optional[dict]:
        """
        解析 SKILL.md 的 YAML frontmatter。

        格式：
        ---
        name: skill-name
        description: ...
        version: 1.0.0
        type: filter
        pipeline: article.before_save
        priority: 10
        trigger: "0 */6 * * *"
        dependencies: []
        ---
        """
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查是否以 --- 开头
        if not content.startswith("---"):
            return None

        # 提取两个 --- 之间的内容
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        frontmatter_str = parts[1].strip()
        if not frontmatter_str:
            return None

        try:
            metadata = yaml.safe_load(frontmatter_str)
            if not isinstance(metadata, dict):
                return None
            return metadata
        except yaml.YAMLError as e:
            print_warning(f"[Skill] YAML 解析错误 {filepath}: {e}")
            return None

    @classmethod
    def _load_skill(cls, skill_dir: str, skill_type: str,
                    metadata: dict, config: dict) -> Optional[BaseSkill]:
        """
        动态加载 skill 模块并实例化。

        Args:
            skill_dir: skill 目录路径
            skill_type: "filter" 或 "job"
            metadata: SKILL.md frontmatter 数据
            config: config.yaml 中该 skill 的配置

        Returns:
            skill 实例
        """
        # 构建模块路径：skills.filter.<name>
        entry_name = os.path.basename(skill_dir)
        module_path = f"skills.{skill_type}.{entry_name}"

        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            print_error(f"[Skill] 导入模块失败 {module_path}: {e}")
            return None

        # 查找模块中的 skill 类（继承自 BaseSkill 的类）
        skill_cls = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                    issubclass(attr, BaseSkill) and
                    attr is not BaseSkill and
                    attr is not FilterSkill and
                    attr is not JobSkill):
                skill_cls = attr
                break

        if skill_cls is None:
            print_error(f"[Skill] 模块 {module_path} 中未找到 Skill 类")
            return None

        # 实例化并设置属性
        skill = skill_cls()
        skill.name = metadata.get("name", entry_name)
        skill.description = metadata.get("description", "")
        skill.version = metadata.get("version", "1.0.0")
        skill.skill_type = skill_type
        skill.enabled = True
        skill.dependencies = metadata.get("dependencies", [])
        skill._skill_dir = skill_dir

        # 类型特有属性
        if isinstance(skill, FilterSkill):
            skill.pipeline = metadata.get("pipeline", "")
            skill.priority = metadata.get("priority", 100)
        elif isinstance(skill, JobSkill):
            skill.trigger = metadata.get("trigger", "")

        # 调用 on_load
        if not skill.on_load(config):
            print_warning(f"[Skill] {skill.name} on_load 返回 False")
            return None

        return skill
