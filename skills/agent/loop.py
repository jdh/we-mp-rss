"""
Agent Loop 主循环

参考 Multi-Agent 四阶段闭环（Plan → Develop → Review → Refine）：
- Planning: LLM 分析任务，选择最合适的 skill（指定 skill_name 时跳过）
- Executing: LLM 分析任务为 skill 组装参数，然后调用执行
- Verifying: 检查执行结果（G5-G7 门禁）
- Reporting: LLM 生成结果报告

核心设计（参考 Harness Engineering）：
- 三支柱：Context Engineering（skill 上下文）+ Architecture（状态机）+ Governance（门禁）
- Agent Contract：文件通信确保可审计
- LLM 全流程参与：选 skill → 组装参数 → 执行 → 验证 → 报告
"""

import json
from typing import Optional, AsyncGenerator

from skills.registry import SkillRegistry
from skills.agent.llm_client import LLMClient
from skills.agent.dispatcher import Dispatcher, AgentState
from core.log import logger
from core.print import print_info, print_warning, print_error


class AgentLoop:
    """
    内置 Agent 循环

    使用方式：
        loop = AgentLoop(agent_config)
        # 方式1：LLM 自动选 skill
        result = await loop.run("帮我清理过期缓存")
        # 方式2：指定 skill，LLM 组装参数并执行
        result = await loop.run("清理过期缓存", skill_name="stale-cache-cleaner")
    """

    def __init__(self, config: dict):
        self.config = config
        self.llm = LLMClient(config)
        self.dispatcher = Dispatcher(
            state_dir=config.get("state_dir", "data/agent_state")
        )
        self.max_turns = config.get("max_turns", 10)
        self.verbose = config.get("verbose", False)

    async def run(self, task: str, skill_name: str = None, params: dict = None) -> dict:
        """
        Agent 循环入口。

        Args:
            task: 用户任务描述
            skill_name: 可选，直接指定 skill（跳过 PLANNING，但仍走 LLM 组装参数）
            params: 可选，直接传入参数（同时跳过 LLM 选 skill 和 LLM 组装参数）

        Returns:
            {"status": "success|failed", "message": "...", "data": {...}}
        """
        self.dispatcher.reset()
        self.dispatcher.task = task

        # 阶段一：PLANNING（指定 skill_name 则跳过）
        if skill_name:
            self.dispatcher.add_history({
                "phase": "planning", "skill": skill_name, "mode": "direct",
            })
        else:
            if not self.dispatcher.transition(AgentState.PLANNING):
                return self._fail_result("无法进入规划阶段")
            skill_name = await self._plan(task)
            if not skill_name:
                self.dispatcher.transition(AgentState.FAILED)
                return self._fail_result("未找到合适的 skill")
            self.dispatcher.add_history({
                "phase": "planning", "skill": skill_name,
            })

        self.dispatcher.selected_skill = skill_name

        # 阶段二：EXECUTING
        if not self.dispatcher.transition(AgentState.EXECUTING):
            return self._fail_result("无法进入执行阶段")

        exec_result = await self._execute(skill_name, task, params)
        self.dispatcher.add_history({
            "phase": "executing", "skill": skill_name, "result": exec_result,
        })

        # 阶段三：VERIFYING
        if not self.dispatcher.transition(AgentState.VERIFYING):
            return self._fail_result("无法进入验证阶段")

        if not self._verify(exec_result):
            self.dispatcher.add_history({
                "phase": "verifying", "passed": False,
                "reason": f"门禁不通过: {exec_result.get('message', '未知')}",
            })
            self.dispatcher.transition(AgentState.FAILED)
            return self._fail_result(f"执行结果验证失败: {exec_result.get('message', '未知错误')}")

        self.dispatcher.add_history({"phase": "verifying", "passed": True})

        # 阶段四：REPORTING - LLM 生成报告
        if not self.dispatcher.transition(AgentState.REPORTING):
            return self._fail_result("无法进入报告阶段")

        report = await self._build_report(task, skill_name, exec_result)
        self.dispatcher.result = report
        self.dispatcher.transition(AgentState.DONE)

        return report

    async def run_stream(self, task: str, skill_name: str = None) -> AsyncGenerator[str, None]:
        """流式执行 Agent 循环"""
        yield self._sse_event("start", {"task": task})
        self.dispatcher.reset()
        self.dispatcher.task = task

        # PLANNING
        if skill_name:
            yield self._sse_event("skill_selected", {"skill": skill_name, "mode": "direct"})
        else:
            yield self._sse_event("phase", {"phase": "planning"})
            self.dispatcher.transition(AgentState.PLANNING)
            skill_name = await self._plan(task)
            if not skill_name:
                yield self._sse_event("error", {"message": "未找到合适的 skill"})
                self.dispatcher.transition(AgentState.FAILED)
                return
            yield self._sse_event("skill_selected", {"skill": skill_name})

        self.dispatcher.selected_skill = skill_name

        # EXECUTING
        yield self._sse_event("phase", {"phase": "executing"})
        self.dispatcher.transition(AgentState.EXECUTING)
        exec_result = await self._execute(skill_name, task)
        yield self._sse_event("executed", {"skill": skill_name, "result": exec_result})

        # VERIFYING
        yield self._sse_event("phase", {"phase": "verifying"})
        self.dispatcher.transition(AgentState.VERIFYING)
        if not self._verify(exec_result):
            yield self._sse_event("error", {"message": "执行结果验证失败"})
            self.dispatcher.transition(AgentState.FAILED)
            return
        yield self._sse_event("verified", {"passed": True})

        # REPORTING
        yield self._sse_event("phase", {"phase": "reporting"})
        self.dispatcher.transition(AgentState.REPORTING)
        report = await self._build_report(task, skill_name, exec_result)
        self.dispatcher.result = report
        self.dispatcher.transition(AgentState.DONE)
        yield self._sse_event("done", report)
        yield self._sse_event("end", {})

    # ---- PLANNING：LLM 选 skill ----

    async def _plan(self, task: str) -> Optional[str]:
        """LLM 分析任务，从可用 skill 中选择最合适的"""
        skills = SkillRegistry.list_all()
        if not skills:
            print_warning("[AgentLoop] 无可用 skill")
            return None

        skill_choices = [s['name'] for s in skills]
        skill_descriptions = "\n".join(
            f"- **{s['name']}** ({s['type']}): {s['description']}" for s in skills
        )

        tools = [{
            "type": "function",
            "function": {
                "name": "select_skill",
                "description": "从可用 skill 列表中选择最合适的一个来执行用户任务",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string", "enum": skill_choices},
                        "reason": {"type": "string"},
                    },
                    "required": ["skill_name", "reason"],
                },
            },
        }]

        messages = [
            {"role": "system", "content": self.llm.build_system_prompt(skill_descriptions, task)},
            {"role": "user", "content": task},
        ]

        try:
            response = await self.llm.chat(messages, tools=tools)
            tool_calls = response.get("tool_calls", [])
            if tool_calls and tool_calls[0]["function"]["name"] == "select_skill":
                args = json.loads(tool_calls[0]["function"]["arguments"])
                logger.info(f"[AgentLoop] LLM 选择: {args.get('skill_name')}, 理由: {args.get('reason', '')}")
                return args.get("skill_name")

            # 兜底：从文本中提取 skill 名
            content = response.get("content", "")
            for s in skills:
                if s['name'] in content:
                    return s['name']
            return None
        except Exception as e:
            logger.error(f"[AgentLoop] PLANNING 失败: {e}")
            return None

    # ---- EXECUTING：LLM 组装参数 + 调用 skill ----

    async def _execute(self, skill_name: str, task: str, params: dict = None) -> dict:
        """
        执行阶段。优先使用传入的 params；否则让 LLM 分析任务为 skill 组装参数。

        对于 FilterSkill：LLM 从任务中提取/构造 content
        对于 JobSkill：LLM 可选覆盖默认参数
        """
        skill = SkillRegistry.get(skill_name)
        if not skill:
            return {"status": "failed", "message": f"Skill 未加载: {skill_name}"}

        from skills.base import FilterSkill, JobSkill

        try:
            # 如果直接传了 params，用它（跳过 LLM 组装参数）
            if params:
                exec_params = params
            else:
                exec_params = await self._llm_build_params(skill, task)

            if isinstance(skill, JobSkill):
                result = skill.execute()
                return result

            elif isinstance(skill, FilterSkill):
                data = exec_params if exec_params else self._extract_filter_data(task)
                result = skill.process(data)
                return {"status": "success", "message": "过滤器执行完成", "data": result}

            else:
                return {"status": "failed", "message": f"未知 skill 类型: {type(skill).__name__}"}

        except Exception as e:
            logger.error(f"[AgentLoop] 执行 skill {skill_name} 失败: {e}")
            return {"status": "failed", "message": str(e)}

    async def _llm_build_params(self, skill, task: str) -> dict:
        """
        让 LLM 分析任务，为指定 skill 生成执行参数。

        返回解析后的参数字典，供 _execute 使用。
        """
        from skills.base import FilterSkill, JobSkill

        skill_info = {
            "name": skill.name,
            "type": skill.skill_type,
            "description": skill.description,
        }

        # 读取 SKILL.md 正文作为上下文
        skill_md = ""
        try:
            with open(f"{skill._skill_dir}/SKILL.md", "r", encoding="utf-8") as f:
                skill_md = f.read()
        except Exception:
            pass

        # 根据 skill 类型构建不同的 function calling 工具
        if isinstance(skill, FilterSkill):
            tools = [{
                "type": "function",
                "function": {
                    "name": "build_filter_params",
                    "description": f"为过滤器 '{skill.name}' 构建输入参数。将用户任务中提到的内容组装成 filter 的输入数据。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "需要处理的内容（HTML/文本）。从用户任务中提取，如果没有则用任务描述本身",
                            },
                            "reason": {
                                "type": "string",
                                "description": "为什么这样构造参数",
                            },
                        },
                        "required": ["content", "reason"],
                    },
                },
            }]
        else:
            # JobSkill 通常不需要额外参数
            tools = [{
                "type": "function",
                "function": {
                    "name": "build_job_params",
                    "description": f"为定时任务 '{skill.name}' 确认执行参数。通常 job skill 不需要额外参数。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "confirm": {
                                "type": "boolean",
                                "description": "确认执行此任务",
                            },
                            "reason": {"type": "string"},
                        },
                        "required": ["confirm", "reason"],
                    },
                },
            }]

        system_prompt = f"""你是一个 skill 执行助手。当前需要执行 skill：

名称：{skill_info['name']}
类型：{skill_info['type']}
描述：{skill_info['description']}

{skill_md}

请分析用户任务，为这个 skill 构建合适的执行参数。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        try:
            response = await self.llm.chat(messages, tools=tools)
            tool_calls = response.get("tool_calls", [])
            if tool_calls:
                args = json.loads(tool_calls[0]["function"]["arguments"])
                logger.info(f"[AgentLoop] LLM 构建参数: {json.dumps(args, ensure_ascii=False)[:200]}")
                return args
            return {}
        except Exception as e:
            logger.warning(f"[AgentLoop] LLM 构建参数失败，使用默认: {e}")
            return {}

    # ---- VERIFYING：门禁检查 ----

    def _verify(self, result: dict) -> bool:
        """G5-G7 门禁"""
        if not isinstance(result, dict):
            logger.error("[AgentLoop] G5: 结果不是 dict")
            return False
        if not result.get("status"):
            logger.error("[AgentLoop] G6: 缺少 status")
            return False
        if result["status"] == "failed":
            logger.error(f"[AgentLoop] G7: status=failed, {result.get('message', '')}")
            return False
        return True

    # ---- REPORTING：LLM 生成报告 ----

    async def _build_report(self, task: str, skill_name: str, result: dict) -> dict:
        """LLM 生成人类可读的执行报告"""
        try:
            messages = [
                {"role": "system", "content": "你是执行结果报告生成器。用简洁的中文总结 skill 执行结果，不超过 200 字。"},
                {"role": "user", "content": f"任务: {task}\nSkill: {skill_name}\n结果: {json.dumps(result, ensure_ascii=False)}"},
            ]
            response = await self.llm.chat(messages)
            summary = response.get("content", f"任务完成: {task}")
        except Exception:
            summary = f"任务完成: {task}"

        return {
            "status": "success",
            "message": summary,
            "data": {
                "task": task,
                "skill": skill_name,
                "result": result,
            },
        }

    # ---- 辅助方法 ----

    def _extract_filter_data(self, task: str) -> dict:
        """从任务描述中提取 HTML/文本内容（兜底方法）"""
        if "```html" in task:
            start = task.index("```html") + 7
            end = task.index("```", start)
            return {"content": task[start:end].strip()}
        if "```" in task:
            start = task.index("```") + 3
            end = task.index("```", start)
            return {"content": task[start:end].strip()}
        return {"content": task, "title": "from_agent_task"}

    @staticmethod
    def _fail_result(message: str) -> dict:
        return {"status": "failed", "message": message}

    @staticmethod
    def _sse_event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
