# Skill 系统设计方案

## 目标

为 we-mp-rss 项目增加运行时业务扩展能力（skill），最小化实现管道/过滤器（filter）和定时任务（job）两种类型。

## 设计原则

- 参考 SKILL.md 三层渐进式披露模式
- 第一版静态配置驱动，预留热管理接口
- 与现有代码共存，不破坏现有逻辑
- 遵循项目现有代码风格

## 架构

```
skills/
├── __init__.py           # Skill 自动发现与注册
├── base.py               # BaseSkill / FilterSkill / JobSkill 抽象基类
├── registry.py           # SkillRegistry 单例注册表
├── filter/               # 管道/过滤器类型 skill
│   └── example_filter/
│       ├── SKILL.md      # YAML frontmatter 元数据
│       └── __init__.py   # 实现代码
└── job/                  # 定时任务类型 skill
    └── example_job/
        ├── SKILL.md
        └── __init__.py
```

## 核心抽象

### BaseSkill
- name, description, version, enabled
- on_load(config) / on_unload()

### FilterSkill (type=filter)
- pipeline: 管道阶段名称（如 article.before_save）
- priority: 执行优先级（数字越小越先）
- process(data) -> data

### JobSkill (type=job)
- trigger: cron 表达式
- execute() -> result

## 注册与发现

### SKILL.md 格式
```markdown
---
name: skill-name
description: 做什么，何时使用
version: 1.0.0
type: filter | job
pipeline: article.before_save  # filter 专用
priority: 10                   # filter 专用
trigger: "0 */6 * * *"        # job 专用
dependencies: []
---
```

### SkillRegistry
- discover(): 扫描目录，只解析 SKILL.md frontmatter（第一级）
- load_enabled(config): 加载配置中启用的 skill（第二级）
- get_filters(pipeline) -> list[FilterSkill]
- get_jobs() -> list[JobSkill]

### config.yaml 配置
```yaml
skills:
  skill-name:
    enabled: true
    # skill 自定义配置...
```

## 集成点

1. **FilterSkill**: 在 `core/article_content.py` 等数据处理链路中调用 `SkillRegistry.get_filters(pipeline)`
2. **JobSkill**: 在 `jobs/__init__.py` 的 `start_job()` 中注册到 TaskScheduler
3. **API**: 可选添加 `apis/skills.py` 查询接口
4. **启动**: `main.py` 中调用 `SkillRegistry.discover()` + `load_enabled()`

## 内置 Agent 循环

参考 Harness Engineering 设计模式：
- **Dispatcher 状态机**：IDLE → PLANNING → EXECUTING → VERIFYING → REPORTING → DONE
- **Agent Contract 握手**：Agent 间通过文件通信（state.json / contract_*.json）
- **G1-G7 门禁**：确定性 Python 函数，fail-closed
- **Function Calling**：LLM 通过 tool call 选择 skill

### Agent Loop 架构
```
skills/agent/
├── __init__.py       # 包入口
├── llm_client.py     # OpenAI 兼容 LLM 客户端
├── dispatcher.py     # Dispatcher 状态机 + Agent Contract
└── loop.py           # Agent Loop 主循环（Plan→Execute→Verify→Report）
```

### API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/wx/skills/ | 列出所有 skill |
| GET | /api/v1/wx/skills/{name} | 查看单个 skill |
| POST | /api/v1/wx/skills/agent/run | Agent 执行（同步/SSE 流式） |
| GET | /api/v1/wx/skills/agent/state | 查看 Agent 状态 |
| POST | /api/v1/wx/skills/agent/reset | 重置 Agent 状态 |

### 使用方式
```bash
curl -X POST http://localhost:8001/api/v1/wx/skills/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "帮我清理过期的缓存文件"}'
```

### 配置
```yaml
agent:
  enabled: true
  api_base: https://api.openai.com/v1
  api_key: sk-xxx
  model: gpt-4o-mini
```

## 不需要改动

- 现有 jobs/、core/、apis/ 代码主体
- 数据库模型
- 前端代码
