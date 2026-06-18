"""
Dispatcher 状态机

参考 Harness Engineering 的 Dispatcher 模式：
- 状态驱动：通过 state.json 追踪执行状态
- 文件交接：Agent 间通过文件通信（Agent Contract）
- 确定性门禁：G1-G8 门禁为确定性 Python 函数

状态机流程：
    IDLE → PLANNING → EXECUTING → VERIFYING → REPORTING → DONE
              ↑            ↓            ↓
              └── FAILED ←─┘ ←─ FAILED ←─┘
"""

import json
import os
import time
from enum import Enum
from typing import Optional

from core.log import logger


class AgentState(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"           # 空闲，等待任务
    PLANNING = "planning"   # 规划阶段：分析任务，选择 skill
    EXECUTING = "executing" # 执行阶段：调用 skill
    VERIFYING = "verifying" # 验证阶段：检查执行结果
    REPORTING = "reporting" # 报告阶段：生成结果报告
    DONE = "done"           # 完成
    FAILED = "failed"       # 失败


class Dispatcher:
    """
    Dispatcher 状态机

    核心设计（参考阿里 Harness 实践）：
    - 主会话退化为"什么都不想、只执行 dispatcher 指令"的纯执行器
    - 状态持久化到 state.json，进程崩了文件在
    - 文件交接保证可审计（git diff 可见）
    """

    # 允许的最大轮次，防止死循环
    MAX_TURNS = 10

    def __init__(self, state_dir: str = "data/agent_state"):
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.state_file = os.path.join(state_dir, "state.json")
        self._state = self._load_state()

    @property
    def state(self) -> AgentState:
        return AgentState(self._state.get("state", "idle"))

    @state.setter
    def state(self, value: AgentState):
        self._state["state"] = value.value
        self._save_state()

    @property
    def task(self) -> Optional[str]:
        return self._state.get("task")

    @task.setter
    def task(self, value: str):
        self._state["task"] = value
        self._save_state()

    @property
    def selected_skill(self) -> Optional[str]:
        return self._state.get("selected_skill")

    @selected_skill.setter
    def selected_skill(self, value: str):
        self._state["selected_skill"] = value
        self._save_state()

    @property
    def turn_count(self) -> int:
        return self._state.get("turn_count", 0)

    @turn_count.setter
    def turn_count(self, value: int):
        self._state["turn_count"] = value
        self._save_state()

    @property
    def result(self) -> Optional[dict]:
        return self._state.get("result")

    @result.setter
    def result(self, value: dict):
        self._state["result"] = value
        self._save_state()

    @property
    def history(self) -> list:
        return self._state.get("history", [])

    def add_history(self, entry: dict):
        """添加执行历史记录"""
        entry["timestamp"] = time.time()
        self._state.setdefault("history", []).append(entry)
        self._save_state()

    def reset(self):
        """重置状态机"""
        self._state = {
            "state": "idle",
            "task": None,
            "selected_skill": None,
            "turn_count": 0,
            "result": None,
            "history": [],
        }
        self._save_state()
        logger.info("[Dispatcher] 状态已重置")

    def transition(self, new_state: AgentState) -> bool:
        """
        状态转换，带门禁检查（G1-G8 门禁）。

        G1: 禁止从 DONE/FAILED 转到非 IDLE 状态
        G2: 最大轮次检查
        G3: 任务不能为空（PLANNING 时）
        G4: skill 不能为空（EXECUTING 时）

        Returns:
            是否允许转换
        """
        current = self.state

        # G1: 终态只能转到 IDLE
        if current in (AgentState.DONE, AgentState.FAILED):
            if new_state != AgentState.IDLE:
                logger.warning(f"[Dispatcher] G1 门禁: 禁止 {current.value} → {new_state.value}")
                return False

        # G2: 最大轮次
        if self.turn_count >= self.MAX_TURNS:
            logger.error(f"[Dispatcher] G2 门禁: 超过最大轮次 {self.MAX_TURNS}")
            self.state = AgentState.FAILED
            return False

        # G3: PLANNING 需要任务
        if new_state == AgentState.PLANNING and not self.task:
            logger.error("[Dispatcher] G3 门禁: 无任务不能进入 PLANNING")
            return False

        # G4: EXECUTING 需要 skill
        if new_state == AgentState.EXECUTING and not self.selected_skill:
            logger.error("[Dispatcher] G4 门禁: 无 skill 不能进入 EXECUTING")
            return False

        logger.info(f"[Dispatcher] 状态转换: {current.value} → {new_state.value}")
        self.state = new_state
        return True

    def get_contract_file(self, agent_name: str) -> str:
        """
        获取 Agent Contract 文件路径（Agent 间文件通信）。

        Agent Contract 模式：一个 Agent 写文件，另一个 Agent 读取。
        """
        filepath = os.path.join(self.state_dir, f"contract_{agent_name}.json")
        return filepath

    def write_contract(self, agent_name: str, data: dict):
        """写入 Agent Contract"""
        filepath = self.get_contract_file(agent_name)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def read_contract(self, agent_name: str) -> Optional[dict]:
        """读取 Agent Contract"""
        filepath = self.get_contract_file(agent_name)
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---- 内部方法 ----

    def _load_state(self) -> dict:
        """从文件加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return self._default_state()

    def _save_state(self):
        """持久化状态到文件"""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _default_state() -> dict:
        return {
            "state": "idle",
            "task": None,
            "selected_skill": None,
            "turn_count": 0,
            "result": None,
            "history": [],
        }
