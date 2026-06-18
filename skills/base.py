"""
Skill 抽象基类定义

参考 SKILL.md 三层渐进式披露模式：
- 第一级：SKILL.md frontmatter（元数据声明）
- 第二级：__init__.py 代码（on_load 时加载）
- 第三级：scripts/references（按需加载，暂未实现）
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseSkill(ABC):
    """所有 skill 的抽象基类"""

    # 从 SKILL.md frontmatter 解析来的属性
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    skill_type: str = ""  # "filter" 或 "job"
    enabled: bool = False
    dependencies: list = []

    # 该 skill 的目录路径，由 registry 设置
    _skill_dir: str = ""

    @abstractmethod
    def on_load(self, config: Optional[dict] = None) -> bool:
        """
        加载时调用，传入该 skill 在 config.yaml 中的配置段。

        Args:
            config: config.yaml 中 skills.<name> 的配置字典

        Returns:
            是否加载成功
        """
        ...

    @abstractmethod
    def on_unload(self) -> bool:
        """卸载时调用，清理资源"""
        ...

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} type={self.skill_type}>"


class FilterSkill(BaseSkill):
    """管道/过滤器类型 skill"""

    skill_type = "filter"

    # 在哪个管道阶段执行
    pipeline: str = ""
    # 同管道内的执行优先级，数字越小越先执行
    priority: int = 100

    @abstractmethod
    def process(self, data: dict) -> dict:
        """
        处理数据，接收一个字典，处理后返回。

        Args:
            data: 输入数据字典

        Returns:
            处理后的数据字典（不修改则原样返回）
        """
        ...

    def on_load(self, config: Optional[dict] = None) -> bool:
        """默认实现：直接返回成功"""
        return True

    def on_unload(self) -> bool:
        """默认实现：直接返回成功"""
        return True


class JobSkill(BaseSkill):
    """定时任务类型 skill"""

    skill_type = "job"

    # cron 表达式，如 "0 */6 * * *"（每6小时执行）
    trigger: str = ""

    @abstractmethod
    def execute(self) -> dict:
        """
        执行任务。

        Returns:
            执行结果字典，包含 status、message 等字段
        """
        ...

    def on_load(self, config: Optional[dict] = None) -> bool:
        """默认实现：直接返回成功"""
        return True

    def on_unload(self) -> bool:
        """默认实现：直接返回成功"""
        return True
