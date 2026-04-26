# Nervus App Platform v0.1 规划

> 目标：在继续开发具体 App 之前，先完成 Nervus 的系统底座第一版。v0.1 不追求 App 产品化，而是让系统具备自我配置、自我描述、自我感知和统一沉淀能力。

---

## 1. 为什么先做平台底座

Nervus 的目标不是做一组孤立 App，而是做一个运行在本地 AI 主机上的个人操作系统。

后续所有 App 最终都会把信息沉淀到个人记忆库和知识库里，并通过模型、事件总线、上下文图谱相互协作。因此，在开发更多 App 前，需要先明确平台层能力：

- App 如何被系统发现、描述、启用和监控
- 本地模型与云端模型如何统一管理
- 事件如何在 App 之间流转
- 处理结果如何统一写入 Memory / Knowledge
- 前端如何展示真实系统状态，而不是硬编码静态 UI

---

## 2. v0.1 的六个底座模块

### 2.1 Config Platform

负责系统配置，避免继续硬编码。

**范围：**

- 主机地址配置
- 外部 Web 演示链接配置
- 本地模型路径配置
- 云端模型 API Key 配置
- 默认模型配置
- App 启用 / 停用配置
- 运行环境配置，如 dev / local / remote

**建议接口：**

```text
GET  /api/config
PATCH /api/config
GET  /api/config/public
```

**说明：**

`/api/config/public` 只返回前端可见配置，例如外部 Web 演示链接、主机显示名、默认入口等，不返回 API Key 等敏感信息。

---

### 2.2 Model Platform

负责本地模型与云端模型统一管理。

**范围：**

- 本地模型列表
- 云端模型列表
- 默认模型
- 当前加载状态
- 模型能力声明
- 模型路由策略
- 隐私 / 成本 / 延迟偏好

**模型能力类型：**

```text
text
vision
audio
embedding
rerank
```

**模型运行位置：**

```text
local
cloud
hybrid
```

**建议接口：**

```text
GET  /api/models
GET  /api/models/status
PATCH /api/models/defaults
POST /api/models/test
POST /api/models/route
```

**路由原则：**

- 隐私敏感内容优先走本地模型
- 长文本、复杂推理、强创作任务可走云端模型
- 本地失败时允许按配置 fallback 到云端
- 云端模型必须显式配置 API Key 后才可使用

---

### 2.3 App Platform

负责 Nervus 原生 App 的注册、发现、状态和能力声明。

**范围：**

- App manifest 规范
- App Registry
- App Health / Status
- App 能力声明
- App 类型区分
- App 生命周期基础状态

**App 类型：**

```text
nervus   # Nervus 原生 App，接入 NSI / NATS / SDK
external # 外部 Web 演示链接，不属于 Nervus 生态
```

**App 状态：**

```text
online
offline
degraded
not_configured
disabled
```

**建议接口：**

```text
GET  /api/apps
GET  /api/apps/{id}
GET  /api/apps/{id}/status
PATCH /api/apps/{id}/settings
```

**manifest 建议字段：**

```json
{
  "id": "meeting-notes",
  "name": "会议纪要",
  "type": "nervus",
  "description": "录音转写、总结和待办提取",
  "icon": "🎙",
  "version": "0.1.0",
  "port": 8002,
  "route": "/api/meeting/",
  "capabilities": {
    "actions": ["transcribe", "summarize", "extract_tasks"],
    "consumes": ["media.audio.created", "media.photo.classified"],
    "emits": ["meeting.processed", "memory.created", "task.created"],
    "models": ["audio", "text"],
    "writes": ["memory", "knowledge"]
  }
}
```

---

### 2.4 Memory / Knowledge Platform

负责个人记忆库与知识库，是 Nervus 的核心沉淀层。

**核心区分：**

```text
Memory
关于用户本人：经历、偏好、关系、状态、计划、人生事件。

Knowledge
用户收集、上传、整理过的外部资料：文件、PDF、文章、网页、RSS、课程、会议材料。
```

**范围：**

- 统一写入 Memory
- 统一写入 Knowledge
- 文件 / 文本 / 事件索引
- 向量化
- 检索
- 上下文构建
- 数据来源追踪

**建议接口：**

```text
POST /api/memory
POST /api/knowledge
POST /api/index
POST /api/memory/search
POST /api/knowledge/search
POST /api/context/build
```

**基础数据类型：**

```text
meeting
note
photo
file
task
calendar_event
preference
life_event
web_article
rss_item
transcript
```

**原则：**

- App 不直接随意写各自的长期记忆结构
- App 通过统一接口提交结构化结果
- Memory / Knowledge Platform 负责持久化、向量化、去重和可追溯性
- Context Graph 只存当前状态，Memory Graph 存长期事实和历史

---

### 2.5 Event / Workflow Platform

负责事件流和跨 App 协作。

**范围：**

- NATS 事件命名规范
- 标准事件结构
- 最近事件流
- Workflow 执行记录
- App 之间的订阅和触发
- Arbor Core 路由和规划记录

**事件命名建议：**

```text
app.started
app.health.changed
model.inference.completed
memory.created
knowledge.indexed
meeting.processed
media.photo.classified
context.user_state.updated
task.created
workflow.started
workflow.completed
workflow.failed
```

**标准事件结构：**

```json
{
  "id": "evt_xxx",
  "type": "meeting.processed",
  "source": "meeting-notes",
  "created_at": "2026-04-26T12:00:00Z",
  "payload": {},
  "trace_id": "trace_xxx",
  "privacy": "local"
}
```

**建议接口：**

```text
GET  /api/events/recent
GET  /api/events/{id}
GET  /api/workflows/recent
GET  /api/workflows/{id}
```

---

### 2.6 Frontend Platform

负责把平台底座以手机 UI 呈现出来。

**范围：**

- 原生应用区从 `/api/apps` 读取
- 外部 Web 演示区从配置读取
- 系统设置页
- 模型管理页
- App 状态页
- 最近事件流
- Memory / Knowledge 基础入口
- 系统健康状态

**原则：**

- 前端不再硬编码原生 App 列表
- 外部演示链接和 Nervus 原生 App 明显区分
- 所有系统状态来自真实接口
- 没有真实数据时显示“未配置 / 未连接”，不再伪造成功状态

---

## 3. v0.1 必做范围

### P0 — 平台定义

- 写清 App manifest v0.1
- 写清 Model config v0.1
- 写清 Memory / Knowledge 基础数据结构
- 写清 Event 标准结构

### P1 — 后端基础接口

- `/api/config/public`
- `/api/apps`
- `/api/apps/{id}/status`
- `/api/models`
- `/api/models/status`
- `/api/events/recent`

### P2 — 前端接入

- 应用中心原生应用区改为读取 `/api/apps`
- 外部 Web 演示区改为读取 public config
- 增加系统状态 / 模型状态基础展示
- 原生 App 点击后进入标准详情页，而不是静态占位提示

### P3 — Memory / Knowledge 最小闭环

- 提供统一写入接口
- 提供最小检索接口
- 先支持文本类内容写入和检索
- 后续再接照片、音频、PDF、RSS 等复杂类型

---

## 4. v0.1 暂时不做

- 不产品化 14 个 App
- 不做复杂自动工作流
- 不做完整人生记忆库 UI
- 不做多用户权限系统
- 不做复杂模型调度算法
- 不做 App 商店 / 插件市场
- 不做云同步

---

## 5. 与现有代码的关系

### 已有基础

- `core/arbor/` 已经是系统中枢雏形
- `core/nats/` 已经提供事件总线
- `core/postgres/` 已经具备 pgvector 基础
- `core/redis/` 已经可作为 Context Graph
- `sdk/python/` 已经被各 App 使用
- `apps/*/` 已经形成独立 Docker App 结构
- `frontend/index.html` 已经有应用中心和五方向导航 UI

### 需要调整

- App Registry 不能继续靠前端硬编码
- App manifest 需要统一并由 Arbor 聚合
- 外部 Web 演示链接需要移出前端代码
- Model 配置需要独立出来
- Memory / Knowledge 写入不能散落在各 App 内部
- Event 命名需要统一
- `docs/porting-guide.md` 需要同步新目录和新 manifest 规范

---

## 6. 建议实施顺序

1. **定义配置文件结构**
   - `config/public.json`
   - `config/models.json`
   - `config/apps.json` 或由 manifest 自动聚合

2. **实现 Arbor 平台接口**
   - config
   - apps
   - models
   - events

3. **统一 manifest**
   - 检查 14 个 App
   - 补齐能力声明
   - 让 Arbor 聚合

4. **前端读取真实平台接口**
   - 原生 App 区
   - 外部 Web 演示区
   - 系统状态区

5. **补 Memory / Knowledge 最小接口**
   - 先支持文本写入、检索、来源追踪

6. **更新 porting guide**
   - 新 App 必须按平台规范接入

---

## 7. v0.1 成功标准

完成 v0.1 后，系统应该做到：

- 前端能看到真实的原生 App 列表和运行状态
- 外部 Web 演示链接不再硬编码在前端
- 系统能展示本地 / 云端模型配置和可用状态
- 每个 App 都有统一 manifest 和 health/status
- 最近事件流可被查看
- App 可以通过统一接口写入 Memory / Knowledge
- 新 App 有清晰模板和接入规范

这时再继续开发具体 App，才不会继续形成新的孤岛。
