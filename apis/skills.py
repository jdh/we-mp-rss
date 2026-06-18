"""
Skill 系统 API

提供 skill 查询和 Agent Loop 交互接口。
Agent Loop 通过 /agent/run 接收自然语言任务，LLM 全流程参与执行。
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from apis.base import success_response, error_response
from skills import SkillRegistry
from skills.agent import AgentLoop
from core.config import cfg
from core.log import logger

router = APIRouter(prefix="/skills", tags=["技能管理"])


class AgentRunRequest(BaseModel):
    task: str
    skill_name: Optional[str] = None
    params: Optional[dict] = None
    stream: bool = False


# ---- Skill 查询接口 ----

@router.get("/")
def list_skills():
    """列出所有已发现的 skill 及其状态"""
    try:
        skills = SkillRegistry.list_all()
        return success_response(data=skills)
    except Exception as e:
        logger.error(f"[Skills API] 列出失败: {e}")
        return error_response(500, str(e))


@router.get("/{name}")
def get_skill(name: str):
    """查看单个 skill 详情"""
    try:
        skill = SkillRegistry.get(name)
        if not skill:
            return error_response(404, f"Skill 未找到: {name}")

        # 读取 SKILL.md 内容
        skill_md_path = f"{skill._skill_dir}/SKILL.md"
        skill_md = ""
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                skill_md = f.read()
        except Exception:
            pass

        return success_response(data={
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "type": skill.skill_type,
            "enabled": skill.enabled,
            "skill_md": skill_md,
        })
    except Exception as e:
        logger.error(f"[Skills API] 获取失败: {e}")
        return error_response(500, str(e))


# ---- Agent Loop 接口 ----

def _get_agent_loop() -> Optional[AgentLoop]:
    """获取 AgentLoop 实例"""
    agent_config = cfg.get("agent", {})
    if not agent_config.get("enabled", False):
        return None

    try:
        return AgentLoop(agent_config)
    except Exception as e:
        logger.error(f"[Skills API] 创建 AgentLoop 失败: {e}")
        return None


@router.post("/agent/run")
async def agent_run(req: AgentRunRequest):
    """
    Agent Loop 执行入口。LLM 全流程参与。

    两种调用方式：

    1. LLM 自动选 skill + 组装参数：
    ```json
    {"task": "帮我清理过期的缓存文件"}
    ```

    2. 指定 skill，LLM 组装参数并执行：
    ```json
    {"task": "清理3天前的缓存", "skill_name": "stale-cache-cleaner"}
    ```

    3. 指定 skill + 参数（跳过 LLM 组装）：
    ```json
    {"task": "清洗内容", "skill_name": "content-sanitizer", "params": {"content": "<div>...</div>"}}
    ```

    支持 stream=true 流式返回进度。
    """
    loop = _get_agent_loop()
    if not loop:
        return error_response(503, "Agent 功能未启用，请在 config.yaml 中配置 agent.enabled=true")

    if req.stream:
        return StreamingResponse(
            loop.run_stream(req.task),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        result = await loop.run(req.task, skill_name=req.skill_name, params=req.params)
        if result["status"] == "success":
            return success_response(data=result["data"])
        else:
            return error_response(500, result.get("message", "执行失败"), data=result.get("data"))
    except Exception as e:
        logger.error(f"[Skills API] Agent 执行失败: {e}")
        return error_response(500, str(e))


@router.get("/agent/state")
def agent_state():
    """获取当前 Agent 状态机的状态"""
    loop = _get_agent_loop()
    if not loop:
        return error_response(503, "Agent 功能未启用")

    state = loop.dispatcher._state
    return success_response(data=state)


@router.post("/agent/reset")
def agent_reset():
    """重置 Agent 状态机"""
    loop = _get_agent_loop()
    if not loop:
        return error_response(503, "Agent 功能未启用")

    loop.dispatcher.reset()
    return success_response(message="状态已重置")
