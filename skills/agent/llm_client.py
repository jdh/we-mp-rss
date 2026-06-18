"""
LLM 客户端

支持 OpenAI 兼容 API，可配置任何兼容的模型服务。
用于 Agent Loop 中的推理决策。
"""

import json
import httpx
from typing import Optional

from core.log import logger
from core.print import print_warning


class LLMClient:
    """OpenAI 兼容的 LLM 客户端"""

    def __init__(self, config: dict):
        """
        Args:
            config: agent 配置段，包含：
                - api_base: API 地址
                - api_key: API 密钥
                - model: 模型名称
                - max_tokens: 最大输出 token
                - temperature: 温度参数
                - timeout: 请求超时秒数
        """
        self.api_base = config.get("api_base", "https://api.openai.com/v1")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gpt-4o-mini")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.1)
        self.timeout = config.get("timeout", 120)

        # 确保 api_base 不以 / 结尾
        self.api_base = self.api_base.rstrip("/")

    async def chat(self, messages: list, tools: Optional[list] = None) -> dict:
        """
        发送对话请求。

        Args:
            messages: 消息列表 [{"role": "system|user|assistant", "content": "..."}]
            tools: 可选的 function calling 工具定义

        Returns:
            {"role": "assistant", "content": "...", "tool_calls": [...]}
        """
        url = f"{self.api_base}/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                choice = data["choices"][0]
                message = choice["message"]

                result = {"role": message.get("role", "assistant")}

                if message.get("content"):
                    result["content"] = message["content"]

                if message.get("tool_calls"):
                    result["tool_calls"] = message["tool_calls"]

                # 记录 token 使用
                usage = data.get("usage", {})
                if usage:
                    logger.info(
                        f"[LLM] {self.model} | "
                        f"prompt={usage.get('prompt_tokens', 0)} "
                        f"completion={usage.get('completion_tokens', 0)} "
                        f"total={usage.get('total_tokens', 0)}"
                    )

                return result

        except httpx.TimeoutException:
            logger.error(f"[LLM] 请求超时 ({self.timeout}s): {url}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[LLM] HTTP 错误 {e.response.status_code}: {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"[LLM] 请求失败: {e}")
            raise

    def build_system_prompt(self, skills_context: str, task_description: str) -> str:
        """
        构建系统提示词（Harness Engineering - Context Harness 层）。

        参考三层渐进式披露：
        - 第一级：skill 列表和描述（始终注入）
        - 第二级：具体 skill 的 SKILL.md body（按需由 agent 自行读取）

        Args:
            skills_context: skill 列表上下文
            task_description: 用户任务描述
        """
        return f"""你是一个微信公众号 RSS 服务（we-mp-rss）的内置 AI 助手。

## 可用能力（Skills）

{skills_context}

## 工作原则

1. 理解用户意图后，选择合适的 skill 执行
2. 如果用户的任务不涉及任何 skill，直接说明并回答
3. 执行 skill 前，先向用户确认操作意图（除非操作完全无副作用）
4. 每次只选择一个最合适的 skill 执行，不要一次调用多个
5. 执行完毕后，用简洁的语言报告结果

## 当前任务

{task_description}
"""
