# Nervus 代谢系统设计：Agent OS 的熵减机制

> 一个真正自主运行的 Agent OS，随着使用时间增长，系统熵增是必然的。
> 路由引擎和执行能力只是「大脑」，**代谢系统**才是让大脑保持清醒的「生命体征」。

---

## 一、问题：Agent OS 的熵增

传统软件系统是静态的——数据库里的数据不会自己"腐烂"，规则不会自己"冲突"。
但 Agent OS 是持续学习和积累的动态系统，熵增无处不在：

### 1.1 记忆熵

| 症状 | 后果 |
|------|------|
| knowledge-base 中堆积过时、矛盾、重复的知识片段 | 语义搜索噪声上升，相关内容被"淹没" |
| 向量索引无限膨胀 | 搜索延迟增大，匹配精度下降 |
| 对话历史无限增长 | 上下文窗口被陈旧信息占据，LLM 推理质量下降 |
| 用户偏好模型停留在早期状态 | 系统"以为它了解你"，但其实已经过时 |

### 1.2 意图熵

| 症状 | 后果 |
|------|------|
| Flow 规则不断累积，彼此冲突 | Fast Router 误命中率上升 |
| 旧 Flow 长期无人触发，但仍参与竞争 | 路由延迟增加，奇怪的误匹配 |
| 提醒、待办事项只增不减 | reminder app 状态膨胀，重要事项被淹没 |

### 1.3 状态熵

| 症状 | 后果 |
|------|------|
| App 内数据（日历、笔记、卡路里）越积越陈旧 | 新决策基于腐烂的基础 |
| 日志无限积累 | 磁盘压力，有效调试信息被稀释 |
| NATS 消息历史和事件队列膨胀 | 内存和存储压力 |

**核心矛盾**：Agent 的价值来自积累，但无管理的积累本身会摧毁这种价值。

---

## 二、设计原则

### 原则一：熵减是主动行为，不是被动清理

不是"满了再删"，而是**持续运行的代谢进程**，就像生物体的新陈代谢。

### 原则二：遗忘是智慧，不是损失

人类记忆系统的核心设计不是"记住一切"，而是**有选择地遗忘**。被频繁访问的记忆得到强化，长期不用的记忆自然衰减。

### 原则三：自我审视是系统能力，不是外部维护

用户不应该需要手动"清理"系统。系统应能定期**自我审视、自我修正**，并将结果透明地呈现给用户确认。

### 原则四：熵减不能破坏上下文一致性

删除一条记忆之前，必须确认它没有被其他记忆或 Flow 引用。代谢操作是**事务性的**。

---

## 三、核心机制

### 3.1 记忆巩固（Memory Consolidation）

**类比**：人类睡眠期间，海马体将短期记忆压缩、转化为长期记忆。

**触发时机**：每日低峰期（默认凌晨 3:00），通过 NATS 调度。

**流程**：

```
每日记忆巩固流程
─────────────────────────────────────────────────────────────
1. 扫描过去 24 小时的对话日志和事件流
   ↓
2. 提取「稳定事实」（用户明确告知 / 多次出现的信息）
   → 写入 knowledge-base，打标签 consolidated=true
   ↓
3. 检测「矛盾条目」（新事实与旧事实语义冲突）
   → 软删除旧条目（标记 deprecated=true，保留 30 天后硬删除）
   ↓
4. 合并「近似重复向量」（cosine similarity > 0.92）
   → 保留访问频率更高的一条，删除另一条
   ↓
5. 将 episodic 日志（具体事件）压缩为 semantic summary
   → 例："本周用户提了 3 次运动目标" → 一条 profile 记录
   ↓
6. 生成巩固报告，写入 NATS: system.metabolism.report
─────────────────────────────────────────────────────────────
```

**实现位置**：`core/arbor/metabolism/consolidation.py`

---

### 3.2 遗忘曲线（Forgetting Curve）

**类比**：Ebbinghaus 遗忘曲线——长期不被访问的记忆逐渐衰减。

所有 knowledge-base 条目和用户 profile 节点都携带一个 `relevance_score`：

```python
# 衰减公式（改进版 Ebbinghaus）
import math

def decay_relevance(base_score: float, days_since_access: int, access_count: int) -> float:
    # 访问次数越多，衰减越慢（稳定性因子）
    stability = 1 + math.log1p(access_count)
    return base_score * math.exp(-days_since_access / (stability * 10))

# 阈值策略
# relevance < 0.3  → 归档（不参与语义搜索，但可查询）
# relevance < 0.1  → 标记待删除，通知用户确认
# 归档后 90 天无访问 → 硬删除
```

**得分重置**：每次通过语义搜索命中或被 Agent 引用时，`relevance_score` 重置为 1.0，`access_count += 1`。

**实现位置**：`core/arbor/metabolism/decay.py`，由后台定时任务（每 6 小时）批量更新。

---

### 3.3 Flow 垃圾回收（Flow GC）

**问题**：Flow 规则只增不减，相互冲突导致路由质量下降。

**触发时机**：每周一次，NATS `system.metabolism.gc`。

**策略**：

```
Flow GC 流程
─────────────────────────────────────────────────────────────
1. 统计过去 30 天每个 Flow 的触发次数
   ↓
2. 触发次数 = 0 的 Flow → 标记为 dormant
   → 在 nervus-cli 显示警告，7 天内无操作则归档
   ↓
3. 检测冲突 Flow 对（两个 Flow 的触发条件语义重叠度 > 0.85）
   → 生成人工审查建议，推送到 nervus-cli
   ↓
4. 合并可合并的 Flow（用户确认后）
─────────────────────────────────────────────────────────────
```

---

### 3.4 系统自审（Self-Reflection Loop）

**类比**：定期体检——系统主动生成"健康报告"，而不是等到出问题才察觉。

**触发时机**：每周日凌晨，LLM 基于系统状态生成报告。

**审视维度**：

```
自审提示词框架（发给云端 LLM）：

系统快照：
  - 知识库条目数：{count}，其中 relevance < 0.3 的：{stale_count}
  - 近 30 天触发的 Flow：{active_flows}，从未触发的：{dormant_flows}
  - 用户交互频率变化趋势：{interaction_trend}
  - 最常访问的 knowledge 类别：{top_categories}

请分析：
  1. 哪些知识领域正在老化，需要用户确认是否仍有效？
  2. 哪些 Flow 可能已经不符合用户当前的使用习惯？
  3. 系统对用户的"理解"有哪些明显的盲点或偏差？
  4. 给出 3 条具体的优化建议。
```

**输出**：在 nervus-cli 以「系统周报」形式推送给用户，支持一键接受/忽略建议。

**实现位置**：`core/arbor/metabolism/reflection.py`

---

### 3.5 日志与状态修剪（Log Pruning）

无需复杂逻辑，策略固定：

| 数据类型 | 保留策略 |
|---------|---------|
| 执行日志（`/logs`） | 保留最近 1000 条，按天归档压缩 |
| NATS 事件历史 | 保留最近 7 天 |
| 对话上下文缓存（Redis） | 每个会话 TTL 24 小时，不活跃会话 6 小时 |
| 通知队列 | 已读通知 24 小时后删除，未读保留 30 天 |

---

## 四、架构集成

### 4.1 新模块结构

```
core/arbor/metabolism/
├── __init__.py
├── scheduler.py        # 代谢任务调度器，监听 NATS system.metabolism.*
├── consolidation.py    # 记忆巩固
├── decay.py            # 遗忘曲线评分更新
├── gc.py               # Flow 垃圾回收
├── reflection.py       # 系统自审
└── pruning.py          # 日志/状态修剪
```

### 4.2 NATS 消息约定

```
system.metabolism.trigger.consolidate   → 触发每日记忆巩固
system.metabolism.trigger.decay         → 触发批量衰减评分更新
system.metabolism.trigger.gc            → 触发 Flow GC
system.metabolism.trigger.reflect       → 触发自审
system.metabolism.trigger.prune         → 触发日志修剪

system.metabolism.report                → 代谢报告（nervus-cli 订阅展示）
system.metabolism.suggestion            → 优化建议（需用户确认）
system.metabolism.suggestion.ack        → 用户确认建议
```

### 4.3 数据库扩展

knowledge-base 条目新增字段：

```sql
ALTER TABLE knowledge_entries ADD COLUMN relevance_score FLOAT DEFAULT 1.0;
ALTER TABLE knowledge_entries ADD COLUMN access_count    INTEGER DEFAULT 0;
ALTER TABLE knowledge_entries ADD COLUMN last_accessed   TIMESTAMP;
ALTER TABLE knowledge_entries ADD COLUMN deprecated      BOOLEAN DEFAULT FALSE;
ALTER TABLE knowledge_entries ADD COLUMN consolidated    BOOLEAN DEFAULT FALSE;
```

### 4.4 nervus-cli 集成

新增快捷键 `Ctrl+M`（F5）：显示系统健康状态面板：

```
─── 系统健康 ───
✓ 知识库     1,247 条  (32 条待归档)
✓ Flow       18 个活跃  (3 个休眠)
✓ 记忆巩固   上次: 今日 03:00
⚠ 系统周报   有 2 条优化建议待确认
```

---

## 五、调度器实现思路

```python
# core/arbor/metabolism/scheduler.py

import asyncio
from datetime import datetime, time as dtime
import nats

SCHEDULE = {
    "consolidate": dtime(3, 0),   # 每日 03:00
    "decay":       None,          # 每 6 小时
    "gc":          "weekly",      # 每周日 02:00
    "reflect":     "weekly",      # 每周日 04:00
    "prune":       dtime(2, 0),   # 每日 02:00
}

class MetabolismScheduler:
    def __init__(self, nc: nats.NATS):
        self.nc = nc

    async def run(self):
        while True:
            now = datetime.now()
            # 检查各任务是否到时间触发
            # ...发布 system.metabolism.trigger.* 消息
            await asyncio.sleep(60)  # 每分钟检查一次
```

---

## 六、设计哲学总结

```
传统软件系统：
  数据 → 永久存储 → 等待查询

Agent OS（无代谢）：
  数据 → 永久积累 → 熵增 → 系统退化

Nervus（有代谢）：
  数据 → 积累 → 巩固 → 衰减 → 遗忘
              ↑                    ↓
              └── 高价值信息强化循环 ──┘
```

Nervus 的真正竞争壁垒不只是「能做什么」，而是**用得越久越聪明、越干净、越懂你**。

代谢系统是实现这个承诺的基础设施。

---

*文档版本：v1.0 | 状态：设计阶段*
