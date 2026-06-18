"""
内置 Agent 循环模块

基于 Harness Engineering 设计模式：
- Dispatcher 状态机（参考 19 节点流程链）
- Agent Contract 握手（文件通信）
- 三层渐进式披露（Skill frontmatter → body → resources）

使用方式：
    from skills.agent import AgentLoop

    loop = AgentLoop(config)
    result = await loop.run("清洗最近3天的文章内容")
"""

from skills.agent.loop import AgentLoop

__all__ = ["AgentLoop"]
