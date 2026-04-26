# Nervus · 完整开发文档

> 本文档是 Nervus 系统的唯一权威参考。覆盖产品灵魂、系统架构、设计规范、开发契约与开发计划。所有开发决策以此为准。
>
> 配合 `mobile/index.html`（单文件 SPA，即全部前端实现）使用。

---

# 第一部分：产品灵魂

## 1.1 问题是什么

今天每个人手机里都有几十个 App。每个 App 都很"聪明"——但只在自己的世界里聪明。

你拍了一张餐厅的照片。热量 App 不知道。
你开完了一个会。会议照片还在相册里睡觉。
你最近压力很大。没有任何 App 感知到，更没有任何 App 调整自己的行为。

信息在孤岛里腐烂，而你充当人肉搬运工。

现有 AI 助理有一个根本性缺陷：它们没有生命周期。你打开它，它存在；你关掉它，它消失。每次对话从零开始，它对你的了解是表演出来的，不是真实积累的。

## 1.2 我们相信什么

**我们相信，真正有价值的 AI 不是被调用的，而是一直在运行的。**

不是你打开 App 才触发 AI，而是 AI 一直在感知、在理解、在连接。

**我们相信，App 应该是器官，而不是工具。**

器官不需要你记得去用它。它自己知道什么时候工作，并且和其他器官协作。

**我们相信，你的数据应该住在你自己家里。**

不上云，不依赖网络，不被第三方持有。一台你的设备，一个你的生态。

**我们坚决不做大模型能力可以直接覆盖的事，不做软件可以轻松替代的事。**

我们只做一件事：**替你承担认知负担，让人重新回归人本身的价值。**

## 1.3 双大脑架构

```
本地小模型（4B）              云端大模型
    慢性记忆                     急性思维

    你睡着的时候                  你需要深度思考的时候
    整理、归档、理解               复杂推理、内容生成
    零成本、离线、持续             按需调用、有成本
    像人的潜意识                  像人的意识
```

本地小模型 24 小时在运转，不是在等你发指令，而是在整理你、理解你、进化自己。它有自己的节律，在你不注意的时候处理信息、巩固记忆、发现规律。

## 1.4 Nervus 是什么

Nervus，拉丁语"神经"。

它不是一个 App，不是一个平台，不是一个助手。**它是连接所有 App 的神经系统。**

Nervus 运行在边缘设备上，永不停止。它让所有 App 共享同一套感知、同一套记忆、同一套行动能力。当你在用某个 App 时，它是这个 App 的 AI 能力。当你没在用任何 App 时，它在后台安静地运行，处理信息，传递数据，更新你的状态。

**你不需要管理信息，信息自己找到它该去的地方。**

## 1.5 两个旗舰体验

### 人生记忆库

**把你的一生，存进一个盒子里。**

自动收集照片、视频、笔记、行程、机票、酒店、听过的歌、看过的电影。自动生成年度回忆录、旅行日志、和重要的人的时间线、孩子成长瞬间集、每年的变化总结。

触动的是"我不想忘记"这个人类最原始的焦虑。

### 私人知识大脑

**你看过的所有东西，都变成你的第二大脑。**

自动收录收藏文章、网页、PDF、书籍、课程笔记、视频字幕、RSS 订阅、会议录音。自动总结重点、生成思维导图、发现跨内容关联，你问它就能答。

**两者共享同一颗大脑**——底层是同一套数据，同一套 AI 理解能力，同一套长期记忆。

## 1.6 一天的生活（系统灵魂的证明）

### 早上 7:23，你还没醒

Nervus 已经工作了一整夜。

昨晚睡前拍的那张床头书的照片，视觉模型识别出书名，自动更新了阅读记录，在知识大脑里创建了这本书的条目。今天 10 点有一个设计评审会议，Nervus 找出了上次相关会议的纪要摘要和相关文档片段，一并准备好了，等你打开会议 App 就能看到。

你不需要做任何事。这些都静默完成了。

### 中午 12:41，你在一家餐厅拍了一张照片

你什么都没做。只是拍了照。

```
[相册扫描器]
  检测到新照片 → 视觉模型分类
  → 识别：意大利面、餐厅环境
  → 发布: media.photo.classified { tags: [food, pasta, restaurant] }

[Nervus Arbor Core]
  结合 Context Graph：今天是工作日午饭时间
  → 快速路由到热量管理 App

[热量管理 App]
  接收事件 → 分析食物热量 → 自动记录 680 kcal
  → 写入 Context Graph: physical.last_meal, physical.calorie_remaining
  → 发布: health.calorie.meal_logged

[人生记忆库]
  同步收到事件 → 将照片归入今日生活流
  → 若今天有旅行行程：自动归入旅行日志
```

你打开热量 App 看了一眼，今天的午餐已经记录好了。你什么都没手动输入。

### 下午 14:00—16:30，设计评审会议

你打开了会议纪要 App，录音开始。两个半小时里，你拍了几张白板的照片。

```
[会议录音 App]
  → faster-whisper 将录音转为文字
  → llama.cpp 生成结构化纪要
  → 发布: meeting.recording.processed { meeting_id, transcript, timestamp_range }

[相册扫描器]
  → 扫描到同时间段照片，识别：白板、会议室
  → 发布: media.photo.classified { tags: [whiteboard, meeting], timestamp ≈ 会议时间 }

[Nervus Arbor Core - 动态规划模式]
  检测到：两事件时间窗口重叠 + 语义高度关联
  → 自主生成执行计划：
    1. 对白板照片做 OCR
    2. 将文字内容整合进会议纪要
    3. 触发重新生成完整报告

[会议纪要 App]
  最终报告：录音纪要 + 白板内容 + 关键决策 + 待办事项
  → 写入 Memory Graph
  → 更新 Context Graph: cognitive.recent_topics
```

### 傍晚，旅行中随手拍了一组照片

```
[相册扫描器]
  → 识别：海边、傍晚
  → 结合 Context Graph：当前有旅行行程记录
  → 发布: memory.travel.moment_captured

[人生记忆库]
  → 归入当前旅行线程
  → 编排时间线
  → 异步触发云端大模型生成旅行日志段落
  → 写入年度回忆录草稿
```

旅行结束后，你会收到一条静默通知："你的旅行日志已经整理好了。"

### 晚上 22:15，系统感知到了什么

你今天压力有点大。

```
[状态感知 App]
  综合信号：消息回复延迟 +38%、文档删改 6 次、会议超时 1h、晚饭延迟 2h
  → 推断: cognitive.load = "high"
  → 发布: context.user_state.updated { field: cognitive.load, value: high }

[日历 App]
  接收状态事件 → 检查明天日程
  → 发现上午有可选例行会议
  → 生成建议：推迟，留出深度工作时间块
  → 明早推送提醒
```

你没有告诉任何人你今天很累。系统自己学会了照顾你。

---

# 第二部分：系统架构

## 2.1 核心比喻

```
这个盒子，是你的第二个自我。

感知器官  →  它的眼睛耳朵      （感知层）
神经系统  →  它的连接          （Synapse Bus）
潜意识    →  本地 AI，慢速持续  （Arbor Core）
意识      →  云端大模型，按需   （急性思维）
长期记忆  →  Memory Graph      （永不遗忘）
工作记忆  →  Context Graph     （当下状态）
```

## 2.2 分层架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      PERCEPTION LAYER  感知层                     │
│                                                                  │
│   相册扫描    麦克风监听    日历感知    RSS订阅    剪贴板    传感器  │
│   (定时轮询)  (会议录音触发) (事件订阅)  (定时拉取) (内容感知) (健康) │
│                                                                  │
│   ← 只做一件事：把现实世界的信号转化为系统内的标准化事件 →           │
└──────────────────────────┬───────────────────────────────────────┘
                           │ 标准化事件流
┌──────────────────────────▼───────────────────────────────────────┐
│                    SYNAPSE BUS  突触总线                           │
│                                                                  │
│                    NATS + JetStream                               │
│                                                                  │
│   media.*    memory.*    meeting.*    context.*    system.*       │
│   health.*   knowledge.* user.*       app.*        schedule.*     │
│                                                                  │
│   ← 所有事件的唯一通道。解耦所有生产者和消费者 →                    │
└───────┬──────────────────┬────────────────────┬──────────────────┘
        │                  │                    │
┌───────▼────────┐  ┌──────▼──────────┐  ┌─────▼────────────────┐
│  ARBOR CORE    │  │  CONTEXT GRAPH  │  │  MEMORY GRAPH        │
│                │  │                 │  │                      │
│  本地AI神经中枢  │  │  用户当下状态    │  │  长期记忆图谱          │
│  llama.cpp     │  │  Redis（实时）   │  │  PostgreSQL          │
│  4B 常驻       │  │                 │  │  + pgvector          │
│                │  │  cognitive.*    │  │                      │
│  理解层         │  │  physical.*     │  │  人生事件              │
│  决策层         │  │  temporal.*     │  │  知识条目              │
│  执行层（Flow） │  │  social.*       │  │  关系图谱              │
│                │  │  travel.*       │  │  向量检索              │
└───────┬────────┘  └─────────────────┘  └──────────────────────┘
        │ 需要深度推理时（约1%场景）
┌───────▼──────────────────────────────────────────────────────────┐
│              CLOUD LLM  云端大模型（急性思维，按需调用）              │
└──────────────────────────────────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────────────────────────┐
│                         APP LAYER  应用层                         │
│                                                                  │
│  [人生记忆库] [知识大脑] [会议纪要] [热量管理] [状态感知] [日历] ...  │
│                                                                  │
│  每个 App 实现 Nervus Standard Interface（NSI）                    │
│  manifest.json / /intake / /emit / /query / /action / /state    │
└──────────────────────────────────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────────────────────────┐
│              MOBILE SHELL  移动端                                 │
│                                                                  │
│   Capacitor.js（iOS 优先）                                        │
│   5面板世界导航 + 所有 App 的 WebView 容器                          │
│   相册/麦克风/后台任务/推送通知  原生插件桥接                         │
└──────────────────────────────────────────────────────────────────┘
```

## 2.3 数据流原则

```
单向流动：感知 → 事件 → 总线 → Arbor → App → Memory/Context

规则：
  ✓ App 通过总线发布事件
  ✓ App 订阅并响应事件
  ✓ App 读取授权范围内的 Context Graph 字段
  ✓ App 写入声明范围内的 Context Graph 字段
  ✗ App 不能直接调用另一个 App（必须通过总线）
  ✗ App 不能直接修改另一个 App 的数据
  ✗ 任何事件不能绕过 Synapse Bus 传递
```

## 2.4 Arbor Core 工作模式

Arbor Core 是整个系统唯一真正"理解"事件的地方，有三种工作模式：

**模式一：快速路由**（约 90% 场景）
事件语义清晰，直接匹配已有流程配置（JSON），触发执行。延迟 < 100ms，无需调用模型。

**模式二：语义路由**（约 9% 场景）
事件需要结合上下文才能判断如何处理。调用 llama.cpp，结合 Context Graph 推理做出路由决策。延迟 < 2s。

**模式三：动态规划**（约 1% 场景）
多个事件产生语义关联，没有预定义流程，Arbor 自主生成执行计划并立即执行。延迟 < 5s。

```
Arbor 只有三个问题：
  1. 这个事件意味着什么？（语义理解）
  2. 谁需要知道这件事？（路由决策）
  3. 应该触发什么行动？（执行规划）
```

流程定义格式（JSON 配置，不是 Node-RED，执行器内置于 Arbor）：

```json
{
  "id": "photo-to-calorie",
  "trigger": "media.photo.classified",
  "condition": { "tags_contains": ["food"] },
  "steps": [
    { "app": "calorie-tracker", "action": "analyze_meal", "input": "$.photo_path" },
    { "context": "set", "field": "physical.last_meal", "value": "$.result.timestamp" },
    { "context": "set", "field": "physical.calorie_remaining", "value": "$.result.remaining" },
    { "emit": "health.calorie.meal_logged", "payload": "$.result" }
  ]
}
```

---

# 第三部分：技术选型

## 3.1 最终技术栈

| 职责 | 技术 | 选择理由 |
|------|------|----------|
| **容器编排** | Docker Compose | 边缘设备一键启动，运维成本最低 |
| **反向代理** | Caddy | 局域网内 HTTPS，自动证书，配置极简 |
| **事件总线** | NATS + JetStream | 专为边缘设计，~10MB 内存，通配符订阅原生支持 |
| **当下状态存储** | Redis | 高频读写 Context Graph，TTL 支持，数据结构丰富 |
| **长期记忆存储** | PostgreSQL + pgvector | 结构化存储 + 向量语义检索，支持跨内容关联 |
| **App 持久化** | SQLite（per App） | 嵌入式，各 App 数据完全自治，无额外服务 |
| **本地 AI 运行时** | llama.cpp server | ARM + CUDA 原生支持，开箱即用，GGUF 格式 |
| **常驻模型** | Qwen3.5-4B 多模态（GGUF） | 文字理解 + 视觉识别合一，无需单独视觉模型 |
| **语音转写** | faster-whisper | 本地离线，速度快，准确率高 |
| **AI 神经中枢** | Python + FastAPI | AI 调用生态最完整，异步处理友好 |
| **工作流执行** | 内置于 Arbor Core | JSON 配置 + Python 执行，无外部依赖 |
| **App 后端** | FastAPI / Fastify | 按 App 技术偏好，均支持异步和标准接口 |
| **移动端壳** | Capacitor.js | 原生能力完整（相册/麦克风/后台任务/推送） |
| **内部 SDK** | nervus-sdk（自研） | 封装基础设施，让 App 开发者 5 行代码接入生态 |

## 3.2 部署环境

**硬件：** NVIDIA Jetson Orin Nano 8GB

- CPU：6核 ARM Cortex-A78AE
- GPU：1024 CUDA Cores（Ampere 架构）
- 内存：8GB 统一内存（CPU + GPU 共享）
- 存储：NVMe SSD（建议 ≥ 256GB）
- 系统：JetPack 6.x（Ubuntu 22.04 + CUDA 12.x）

## 3.3 内存预算

```
总可用：8GB 统一内存

分配：
  JetPack 系统底层                  ~1.5GB
  Qwen3.5-4B 多模态 INT4            ~2.8GB  ← 文字+视觉合一，常驻
  faster-whisper（按需）            ~0.5GB  ← 按需加载，用完释放
  Redis                             ~200MB
  PostgreSQL                        ~300MB
  NATS                              ~50MB
  Caddy                             ~30MB
  Arbor Core (Python)               ~200MB
  20个 App 后端 (avg 50MB)          ~1.0GB
  Docker overhead                   ~200MB
  ───────────────────────────────────────
  常驻总计（无语音）                 ~6.3GB
  峰值（转写任务进行中）             ~6.8GB  ← 安全边界内

优势（相比双模型方案）：
  移除 minicpm-v，节省约 1.5GB
  视觉调用无需切换模型，延迟更低
  内存压力显著下降，峰值远离 8GB 边界
```

---

# 第四部分：前端设计系统

> 本部分直接来源于 `app-prototype.html` 的实现，所有开发必须严格遵守。

## 4.1 导航结构

采用 **5 宫格世界坐标**系统。`.panels` 是一块 3×3 面板宽高的大画布，`.viewport` 在上面平移，每次只显示一个格子。

```
         [感知页 p-sense]
              ↑ 下拉（手指向下）
[对话页] ← [主页 p-home] → [文件管理 p-files]
 p-chat  左划(手指左)  右划(手指右)
              ↓ 上推（手指向上）
         [应用中心 p-apps]
```

| 面板 | CSS ID | 进入手势 | JS 条件 |
|------|--------|----------|---------|
| 主页（默认） | `#p-home` | 从任意方向返回 | — |
| AI 感知 | `#p-sense` | 主页**下拉**（手指向下，dy > 0） | `dy > 0 && current === 'home'` |
| AI 对话 | `#p-chat` | 主页**向左划**（手指向左，dx < 0） | `dx > 0 && current === 'home'` |
| 文件管理 | `#p-files` | 主页**向右划**（手指向右，dx > 0） | `dx < 0 && current === 'home'` |
| 应用中心 | `#p-apps` | 主页**上推**（手指向上，dy < 0） | `dy < 0 && current === 'home'` |

> 手势方向以**手指移动方向**为准：手指向下（dy > 0）= 下拉，手指向上（dy < 0）= 上推。

**手势实现规范：**
```
touchstart → 记录起点 (sx, sy)
touchend   → 计算 dx = ex-sx, dy = ey-sy
绝对位移 > 55px 且主轴更大 → 触发导航切换

注意：passive: true（不阻止原生滚动）
      .app-screen.open 时，面板手势完全禁用
```

**面板坐标（CSS）：**
```css
#p-sense { left: var(--PW); top: 0 }           /* 第0行 */
#p-chat  { left: 0;          top: var(--PH) }  /* 第1行，第0列 */
#p-home  { left: var(--PW);  top: var(--PH) }  /* 第1行，第1列（默认） */
#p-files { left: calc(var(--PW)*2); top: var(--PH) }
#p-apps  { left: var(--PW);  top: calc(var(--PH)*2) }
```

**面板切换动画：**
```css
.panels {
  transition: transform 460ms cubic-bezier(.32,.72,0,1);
}
```

**JS 导航函数：**
```js
function nav(name) {
  PW = window.innerWidth;
  PH = viewportEl.clientHeight;   // 安全区域后的实际高度，非 innerHeight
  const [col, row] = PANEL_GRID[name];
  panelEl.style.transform = `translate(${-col*PW}px,${-row*PH}px)`;
  current = name;
}
```

## 4.2 色彩规范

| Token | 深色模式 | 浅色模式 | 说明 |
|-------|----------|----------|------|
| `--bg` | `#07070E` | `#F2F2F7` | 背景色 |
| `--bg-blur` | `rgba(7,7,14,.88)` | `rgba(242,242,247,.92)` | 毛玻璃背景 |
| `--s1` | `rgba(255,255,255,.04)` | `rgba(0,0,0,.04)` | 表面层 1 |
| `--s2` | `rgba(255,255,255,.07)` | `rgba(255,255,255,.72)` | 表面层 2（卡片） |
| `--s3` | `rgba(255,255,255,.12)` | `rgba(0,0,0,.08)` | 表面层 3 |
| `--border` | `rgba(255,255,255,.07)` | `rgba(0,0,0,.07)` | 主边框 |
| `--border2` | `rgba(255,255,255,.13)` | `rgba(0,0,0,.12)` | 次边框 |
| `--text` | `#EEEEF8` | `#1C1C1E` | 主文本 |
| `--text2` | `rgba(238,238,248,.55)` | `rgba(28,28,30,.55)` | 次文本 |
| `--text3` | `rgba(238,238,248,.28)` | `rgba(28,28,30,.35)` | 辅助文本 |
| `--accent` | `#8B72FF` | `#6B52F0` | 主强调色（紫） |
| `--teal` | `#5EEAB5` | `#00C896` | 辅助色（青绿） |
| `--orange` | `#FFAA5C` | `#E0820A` | 警示色（橙） |
| `--red` | `#FF6E7A` | `#E8344A` | 危险色（红） |

主题根据 `prefers-color-scheme` 自动切换，无需手动控制。

**实现要点：**
```html
<!-- 必须声明双主题支持，否则 WKWebView 不响应系统切换 -->
<meta name="color-scheme" content="light dark">
<meta name="theme-color" media="(prefers-color-scheme:dark)"  content="#07070E">
<meta name="theme-color" media="(prefers-color-scheme:light)" content="#F2F2F7">
```
```css
:root {
  color-scheme: light dark;   /* 让原生表单、滚动条等元素也跟随主题 */
}
@media (prefers-color-scheme: light) {
  :root { /* 覆盖浅色主题变量 */ }
}
```
iOS 状态栏文字颜色通过 `MainViewController.swift` 的 `preferredStatusBarStyle` 随系统切换。

## 4.3 字体规范

主字体栈：`'PingFang SC', 'Outfit', -apple-system, sans-serif`

数字/英文标题使用 Outfit（Google Fonts），中文使用 PingFang SC。

| 用途 | 字号 | 字重 |
|------|------|------|
| 大标题 | 22–24px | 800 |
| 页面标题 | 17–18px | 700 |
| 卡片标题 | 14–15px | 600 |
| 正文 | 13–14px | 400–500 |
| 辅助文字 | 11–12px | 400–500 |
| 微标签 | 9–10px | 600，`text-transform: uppercase` |

## 4.4 圆角规范

| 元素 | 圆角值 |
|------|--------|
| 手机外框 / App Screen | 52px |
| 大卡片（gc） | 24px |
| 普通卡片 | 20px |
| 按钮 / 胶囊 | 25px（完全圆角） |
| 输入框 | 12–16px |
| 应用图标 | 16px |
| 图片内容 | 12px |
| 标签 / chip | 20px |

## 4.5 毛玻璃效果

```css
/* 标准配方 */
background: var(--s2);
border: 1px solid var(--border);
border-radius: Xpx;
backdrop-filter: blur(20px);
-webkit-backdrop-filter: blur(20px);

/* 导航栏额外加 */
border-bottom: 1px solid var(--border);
```

## 4.6 叠层卡片阴影

模拟背后有多张卡的视觉效果（设计语言的核心）：

```css
/* 大卡 gc */
box-shadow: 0 5px 0 -2px var(--s2),  0 5px 0 -1px var(--border2),
            0 10px 0 -4px var(--s1), 0 10px 0 -3px var(--border2);

/* 小卡 qc */
box-shadow: 0 4px 0 -2px var(--s2),  0 4px 0 -1px var(--border),
            0 8px 0 -4px var(--s1),  0 8px 0 -3px var(--border2);
```

## 4.7 动效规范

| 用途 | 曲线 | 时长 |
|------|------|------|
| 面板导航切换 | `cubic-bezier(.32,.72,0,1)` | 460ms |
| App 打开/关闭 | `cubic-bezier(.32,.72,0,1)` | 460ms |
| 详情页滑入 | `cubic-bezier(.32,.72,0,1)` | 380ms |
| 卡片内容进入 | `cubic-bezier(.32,.72,0,1)` | 420ms |
| 卡片内容退出 | `ease-in` | 280ms |
| 快速 UI 响应 | `ease` | 150–180ms |

**叠层卡片切换动画三步：**

```
1. 退出 (280ms ease-in):
   transform: scale(0.91) translateY(-10px)
   opacity: 0
   filter: blur(2px)

2. 立即重置 (no transition):
   transform: scale(0.91) translateY(14px)
   opacity: 0

3. 进入 (420ms cubic-bezier(.32,.72,0,1)):
   transform: scale(1) translateY(0)
   opacity: 1
   filter: blur(0)
```

## 4.8 安全区域

Nervus 运行在真实全屏环境（`viewport-fit=cover`），无模拟手机壳，需正确处理 Dynamic Island / 刘海 / Home Indicator 区域。

### 顶部安全区（Dynamic Island / 刘海）

**核心做法：** `.viewport` 整体下移 `env(safe-area-inset-top)` 像素，所有面板内容自然从安全区下方开始，无需每个元素单独偏移。

```css
/* CSS 变量（初始值 0，JS 启动后写入真实像素值） */
:root { --SAT: 0px; }

/* viewport 整体下移 */
.viewport {
  position: absolute;
  top: env(safe-area-inset-top, 0px);
  left: 0; right: 0; bottom: 0;
  overflow: hidden;
}

/* 面板高度 = 屏幕高度 − 安全区 */
:root { --PH: calc(100dvh - var(--SAT)); }
```

```js
// 启动时用探针精确测量，写回 --SAT 和 viewport.style.top
function applySafeArea() {
  const probe = document.createElement('div');
  probe.style.cssText = 'position:fixed;top:env(safe-area-inset-top,0px);height:0;visibility:hidden';
  document.body.appendChild(probe);
  const sat = probe.getBoundingClientRect().top;
  probe.remove();
  if (sat > 0) {
    document.documentElement.style.setProperty('--SAT', sat + 'px');
    viewportEl.style.top = sat + 'px';
  }
}
```

### 各面板顶部留白规范（viewport 内，无需再加 safe-area-inset）

| 面板 | 实现方式 | 顶部留白 |
|------|---------|---------|
| 主页 | `.hc` padding-top | 24px |
| 感知 | `.sense-scroll` top | 8px |
| 对话 | `.chat-hdr` height | 52px |
| 文件 | `.files-hdr` height | 52px |
| 应用 | `.apps-c` padding-top | 22px |

### 底部安全区（Home Indicator）

底部输入栏和可滚动内容末尾使用 `env(safe-area-inset-bottom)` 保留 Home Indicator 空间：

```css
padding-bottom: max(20px, calc(env(safe-area-inset-bottom) + 10px));
```

### 面板隔离（z-index 穿透防护）

每个 `.panel` 必须设置 `isolation: isolate`，否则面板内高 `z-index` 元素（如语音 Orb 的 `z-index:60`）会穿透到相邻面板上方。

```css
.panel {
  position: absolute;
  width: var(--PW);
  height: var(--PH);
  overflow: hidden;
  isolation: isolate;   /* 关键：限制 z-index 作用域在本面板内 */
}
```

---

# 第五部分：应用清单与规格

## 5.1 主 Shell 五个面板

### 主页（p-home）

布局从上到下：

```
[状态栏 58px]
[AI 摘要大卡 gc]  ← 5组内容轮播，每 6.2s 切换
[两列快捷卡 qrow] ← 左卡 7.8s，右卡 9.3s，错开计时
[待确认提醒条 remind-bar]
[AI 语音 Orb 区域 vbw] ← 固定底部
```

**AI 摘要大卡轮播内容（5组）：**

| 组 | 标题 | 展示内容 |
|----|------|----------|
| 今日摘要 | AI 助手 · 今日摘要 | 跨应用同步次数、照片归档、知识库关联 |
| 昨夜后台 | AI 助手 · 昨夜后台 | 系统睡着后完成的任务 |
| 跨应用联动 | AI 助手 · 跨应用联动 | 照片→热量、录音+白板→纪要 |
| 记忆图谱 | AI 助手 · 记忆图谱 | 知识积累数量、关联节点、专注排名 |
| 今夜计划 | AI 助手 · 今夜计划 | 入睡后系统将完成的任务 |

**AI 语音 Orb：**
- 渐变背景：`linear-gradient(270deg, #8B72FF, #5EEAB5, #FFAA5C, #FF6E7A, #8B72FF)` background-size 400%，6s 动画
- 3层脉冲环：延迟 0/0.85s/1.7s，scale(.82→1.42)，3s 无限
- 建议 Chip 每 4s 轮换（6组内容）

### AI 感知页（p-sense）

展示系统从多个 App 行为信号推断出的用户状态，非用户手动输入。

```
① 状态主球（综合得分 + 状态描述）
② 四格状态卡（认知负荷 / 体力 / 情绪 / 睡眠）
③ Nervus 今日事件流（时间线，系统后台完成的每件事）
④ 认知负荷推断依据（4个信号可视化）
⑤ 今日精力曲线（时间轴横条图）
⑥ 今日时间线（用户行为 + AI 事件混合）
⑦ 本周专注规律（7天对比）
⑧ Nervus 今夜计划（入睡后将处理的任务）
⑨ Nervus 建议（基于 Context Graph 的行动建议）
```

**关键：** 感知页所有数据来自 Context Graph 实时读取，不是静态数据。

### AI 对话页（p-chat）

- 顶部：AI 头像 + 名称「AI 助手」+ 状态「边缘设备在线 · 4B 模型」
- 消息流：AI 靠左，用户靠右
- 底部：麦克风 + 输入框 + 发送
- 用户发送消息后，900ms 内回复「好的，我正在处理…」

### 文件管理页（p-files）

微信文件传输助手风格：右对齐气泡，时间线展示。

消息卡片类型：

| 类型 | max-width | 说明 |
|------|-----------|------|
| 文件卡片 | 255px | 左侧图标，文件名+大小 |
| 链接卡片 | 248px | 缩略图+标题+来源域名 |
| 图片卡片 | 185px | 185×120 圆角图片 |
| 文字气泡 | 220px | accent 色背景 |

底部输入：浮动胶囊（`bottom:16px; left:16px; right:16px`），含 📷📎🔗 + 输入 + 发送。

### 应用中心（p-apps）

4列网格，图标 64×64px，圆角 16px，下方 10.5px 名称。

## 5.2 应用完整列表

| # | 应用 | 图标 | 原型状态 | Nervus 集成 |
|---|------|------|----------|-------------|
| 1 | 开发规范 | 📐 | 完整 | 无需集成 |
| 2 | 提醒 | 📋 | 完整 | 订阅 `schedule.*`，写入 Context |
| 3 | 会议纪要 | 🎙 | 完整 | 发布 `meeting.recording.processed` |
| 4 | PDF 提取 | 📄 | 完整 | 发布 `knowledge.document.indexed` |
| 5 | 密码本 | 🔐 | 完整 | 本地加密存储，不接事件总线 |
| 6 | 视频转录 | 🎬 | 完整 | 发布 `knowledge.video.transcribed` |
| 7 | 热量管理 | 🔥 | 完整 | 订阅 `media.photo.classified`，写入 Context |
| 8 | MBTI 陪伴 | ✨ | 完整 | 读取 Context 用户状态，调整对话风格 |
| 9 | 个人笔记 | 📝 | 完整 | 发布 `knowledge.note.created` |
| 10 | 文件管理 | 🗂 | 完整（Shell） | 触发 Nervus 全局弹窗 |
| 11 | 工作流 | ⚡ | 待开发 | 可视化查看/编辑 Arbor 流程配置 |
| 12 | 闹钟 | ⏰ | 待开发 | 订阅 `context.user_state.updated`（睡眠数据） |
| 13 | 日历 | 📅 | 待开发 | 订阅 `context.user_state.updated`，推送调整建议 |
| 14 | 知识库 | 📚 | 待开发 | 订阅所有 `knowledge.*`，统一展示/问答 |
| 15 | RSS 订阅 | 📡 | 待开发 | 发布 `knowledge.article.fetched` |
| 16 | 勋章系统 | 🏅 | 待开发 | 订阅各类行为事件，累计成就 |
| 17 | 电子宠物 | 🐣 | 待开发 | 读取 Context 状态，反映用户真实状态 |
| 18 | 健康趋势 | 💚 | 待开发 | 读取 Memory Graph 历史健康数据 |
| 19 | 相册处理 | 🖼 | 待开发 | 触发 `media.photo.classified` 批量处理 |
| 20 | 人生记忆库 | 📖 | 待开发 | 订阅 `memory.*`，写入 Memory Graph |

## 5.3 各 App 核心规格

### 会议纪要 App

- 波形可视化录音按钮，录音中显示脉冲动画
- 录音完成后调用 faster-whisper 转写 + llama.cpp 生成纪要
- 生成报告：纪要标题 / 摘要 / 关键决策 / 待办事项
- **关键集成：** 白板照片与录音时间窗口交叉匹配，自动整合进纪要

### 热量管理 App

- 今日热量圆形进度环（SVG，渐变描边）
- 三餐卡片**自动填入**（来自照片识别，无需手动输入）
- 营养素占比（蛋白质/碳水/脂肪）
- **关键：** 拍照 → 自动识别 → 自动记录，零操作

### 个人笔记 App

两个视图（列表 ↔ 详情从右侧滑入）：
- 列表：固定笔记、分区显示（今天/昨天/本周）、搜索
- 详情：标题居中输入、正文 textarea、底部格式工具栏（加粗/斜体/下划线/列表/勾选框）
- 返回逻辑：详情中 ‹ 返回列表，列表中 ‹ 关闭 App

### Nervus 全局弹窗

触发条件：系统检测到新文件，或文件管理页点击文件。

内容：
```
标题：「Nervus 检测到新文件」
来源：「来自 AirDrop · X分钟前 · 已完成预处理」
文件信息：文件名 / 大小 / 页数

Nervus 已分析：
  · PDF 解析完成，提取关键词 N 个
  · 与历史内容相似度 X%
  · 检测到 N 个待办项

操作按钮：
  [主] 写入知识大脑 + 生成摘要
  [次] 关联本次会议
  [次] 提取 N 个待办
```

这个弹窗是 **系统灵魂的最直接体现**——Arbor Core 后台分析完成后主动推送，用户打开手机就看到系统已经帮你做完了理解工作。

---

# 第六部分：开发契约（NSI）

## 6.1 NSI 接口规范

每个接入 Nervus 生态的 App 必须实现以下接口：

```
GET  /manifest        返回 App 的能力声明
POST /intake          接收来自 Arbor 或其他 App 的数据
POST /emit            向总线发布事件（通过 nervus-sdk）
GET  /query/:type     回答关于自身数据的查询
POST /action/:name    执行具体能力
GET  /state           暴露当前状态快照
```

## 6.2 manifest.json 规范

```json
{
  "id": "calorie-tracker",
  "name": "热量管理",
  "version": "1.0.0",
  "description": "AI 自动记录饮食，跟踪热量目标",

  "subscribes": [
    {
      "subject": "media.photo.classified",
      "filter": { "tags_contains": ["food"] },
      "handler": "/intake/photo_classified"
    }
  ],

  "publishes": [
    "health.calorie.meal_logged",
    "health.calorie.budget_alert"
  ],

  "actions": [
    {
      "name": "analyze_meal",
      "description": "分析食物照片并返回热量信息",
      "input": { "photo_path": "string" },
      "output": { "calories": "number", "food_name": "string" }
    }
  ],

  "context_reads": [
    "physical.daily_calorie_budget",
    "physical.calorie_remaining"
  ],

  "context_writes": [
    "physical.last_meal",
    "physical.calorie_remaining"
  ],

  "memory_writes": [
    "health.meal_history"
  ]
}
```

## 6.3 Synapse Bus 事件表

| 事件主题 | 发布者 | 主要订阅者 | 说明 |
|----------|--------|-----------|------|
| `media.photo.classified` | 相册扫描器 | 热量管理、人生记忆库 | 照片 AI 分类完成 |
| `media.photo.batch_processed` | 相册处理 App | 人生记忆库 | 批量相册处理完成 |
| `meeting.recording.processed` | 会议纪要 | Arbor、知识库 | 录音转写+纪要生成完成 |
| `meeting.whiteboard.detected` | 相册扫描器 | 会议纪要 | 检测到白板照片（时间匹配） |
| `health.calorie.meal_logged` | 热量管理 | 状态感知、提醒 | 饮食记录写入 |
| `health.calorie.budget_alert` | 热量管理 | 提醒 | 热量超出预算 |
| `context.user_state.updated` | 状态感知 | 日历、Arbor | 用户状态字段更新 |
| `memory.travel.moment_captured` | 相册扫描器 | 人生记忆库 | 旅行照片捕捉 |
| `memory.annual.review_ready` | 人生记忆库 | 通知系统 | 年度回忆录生成完成 |
| `knowledge.document.indexed` | PDF提取/知识库 | 知识库 | 文档向量化完成 |
| `knowledge.article.fetched` | RSS 订阅 | 知识库 | 新文章获取 |
| `knowledge.note.created` | 个人笔记 | 知识库 | 新笔记创建 |
| `knowledge.video.transcribed` | 视频转录 | 知识库 | 视频转文字完成 |
| `system.app.registered` | Arbor | 所有 App | App 上线注册 |
| `system.file.detected` | 文件管理 | Arbor | 新文件进入系统 |
| `schedule.reminder.triggered` | 提醒 App | 日历 | 提醒时间到达 |

**主题命名规范：**
```
{domain}.{entity}.{verb}

domain:   media / meeting / health / context / memory / knowledge / system / schedule
entity:   photo / recording / calorie / user_state / travel / document / app / reminder
verb:     classified / processed / logged / updated / captured / indexed / detected
```

## 6.4 Context Graph 字段表

Context Graph 是系统的"工作记忆"，存储在 Redis，所有 App 共享读写（声明范围内）。

```yaml
context:user:
  temporal:                        # 时间维度
    current_schedule: string       # 当前在做什么（来自日历 App）
    upcoming_events: list          # 接下来的安排
    day_type: string               # workday / weekend / holiday
    time_of_day: string            # morning / afternoon / evening / night

  physical:                        # 身体维度
    location_type: string          # home / office / restaurant / travel / outdoor
    activity: string               # sedentary / walking / exercise / commuting
    last_meal: timestamp           # 上次进餐时间
    calorie_remaining: number      # 今日剩余热量预算
    daily_calorie_budget: number   # 每日热量目标
    sleep_last_night: number       # 昨夜睡眠时长（小时）

  cognitive:                       # 认知维度
    load: string                   # low / medium / high
    current_focus: string          # 当前关注的主题（来自 Arbor 推断）
    recent_topics: list            # 最近涉及的话题
    decision_fatigue: string       # low / medium / high

  social:                          # 社交维度
    communication_mode: string     # active / quiet / dnd
    recent_meeting: object         # 最近会议信息

  travel:                          # 旅行维度
    is_traveling: boolean
    current_trip: object           # { name, start_date, moments_count }

  _app:                            # 各 App 私有命名空间（前缀隔离）
    calorie-tracker.*: ...
    meeting-notes.*: ...
    ...
```

**TTL 规则：**
- `temporal.*`：6小时自动过期
- `physical.*`：24小时自动过期
- `cognitive.*`：12小时自动过期
- `_app.*`：各 App 自定义 TTL

## 6.5 Memory Graph Schema（PostgreSQL）

```sql
-- 人生事件表
CREATE TABLE life_events (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type        TEXT NOT NULL,          -- photo / meeting / meal / travel / note
  title       TEXT,
  description TEXT,
  timestamp   TIMESTAMPTZ NOT NULL,
  source_app  TEXT,
  metadata    JSONB,
  embedding   vector(1536),           -- pgvector，用于语义召回
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 知识条目表
CREATE TABLE knowledge_items (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type        TEXT NOT NULL,          -- article / pdf / video / note / meeting
  title       TEXT NOT NULL,
  content     TEXT,
  summary     TEXT,
  source_url  TEXT,
  tags        TEXT[],
  timestamp   TIMESTAMPTZ NOT NULL,
  embedding   vector(1536),
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 关系图谱表
CREATE TABLE item_relations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id   UUID NOT NULL,
  target_id   UUID NOT NULL,
  relation    TEXT NOT NULL,          -- related_to / part_of / generated_from
  weight      FLOAT DEFAULT 1.0,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 向量索引
CREATE INDEX ON life_events   USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON knowledge_items USING ivfflat (embedding vector_cosine_ops);
```

## 6.6 nervus-sdk API（Python）

```python
from nervus_sdk import NervusApp, Context, emit

app = NervusApp("calorie-tracker")

# 订阅事件（带过滤条件）
@app.on("media.photo.classified", filter={"tags_contains": ["food"]})
async def handle_food_photo(event: Event):
    result = await app.call_action("calorie-tracker", "analyze_meal",
                                   photo_path=event.payload.photo_path)
    await Context.set("physical.last_meal", event.timestamp)
    await Context.set("physical.calorie_remaining",
                      (await Context.get("physical.calorie_remaining")) - result.calories)
    await emit("health.calorie.meal_logged", result.dict())

# 声明 Action
@app.action("analyze_meal")
async def analyze_meal(photo_path: str) -> MealAnalysis:
    # 文字和视觉用同一个模型，同一个接口
    response = await app.llm.vision(
        image_path=photo_path,
        prompt="识别图片中的食物名称，并估算热量（kcal）"
    )
    return MealAnalysis(**response)

# 暴露状态
@app.state
async def get_state() -> dict:
    ctx = await Context.get_namespace("calorie-tracker")
    return {"today_calories": ctx.get("today_total", 0)}

# 启动
app.run(port=8001)
```

**nervus-sdk TypeScript 版本：**

```typescript
import { NervusApp, Context, emit } from '@nervus/sdk'

const app = new NervusApp('calorie-tracker')

app.on('media.photo.classified',
  { filter: { tags_contains: ['food'] } },
  async (event) => {
    const result = await analyzeMeal(event.payload.photoPath)
    await Context.set('physical.last_meal', event.timestamp)
    await emit('health.calorie.meal_logged', result)
  }
)

app.action('analyze_meal', async ({ photoPath }) => {
  return await visionModel.analyze(photoPath)
})

app.run({ port: 8001 })
```

---

# 第七部分：开发计划

## Sprint 0 — 基础设施（第 1 周）

**目标：** 所有基础服务在 Jetson 上跑起来，能互相通信。

```
□ Docker Compose 骨架（所有服务定义，统一网络）
□ NATS + JetStream 部署和配置
□ Redis 部署（Context Graph 初始 schema）
□ PostgreSQL + pgvector 部署（Memory Graph schema 建表）
□ llama.cpp server 编译安装（针对 JetPack/CUDA 优化）
□ qwen2.5:4B-Q4_K_M 模型下载和加载测试
□ faster-whisper 服务部署
□ minicpm-v 模型准备（暂不常驻）
□ Caddy 配置反向代理（局域网 HTTPS）
□ 内存基准测试（确认 8GB 边界安全）
□ docker-compose.yml 完整版本提交

验收：
  curl llama.cpp → 返回 AI 回复
  NATS 发布/订阅测试通过
  Redis 读写测试通过
  PostgreSQL 建表成功，pgvector 扩展安装
  内存峰值 < 6GB（常驻状态）
```

## Sprint 1 — nervus-sdk（第 2 周）

**目标：** 开发者能用 SDK 5 行代码接入生态。

```
□ manifest.json 完整 schema（含校验）
□ Python SDK：
    NervusApp 类
    Context 读写（Redis 封装）
    emit() 发布事件（NATS 封装）
    @app.on() 订阅装饰器
    @app.action() 能力声明装饰器
    @app.state 状态暴露装饰器
    app.llm.chat() 文字理解调用（Qwen3.5-4B 多模态）
    app.llm.vision() 视觉理解调用（同一模型，传入图片+提示词）
    app.whisper faster-whisper 语音转写封装
□ TypeScript SDK（同等功能）
□ NSI 标准接口自动挂载（manifest/intake/emit/query/action/state）
□ SDK Demo App（最小可运行示例）
□ App 注册机制（启动时向 system.app.registered 发布）

验收：
  Demo App 启动 → 订阅事件 → 收到事件 → 写入 Context → 发布事件
  全链路延迟 < 200ms（不含 AI 调用）
```

## Sprint 2 — Arbor Core（第 3–4 周）

**目标：** 神经中枢能理解事件并做出路由决策。

```
□ FastAPI 服务骨架
□ NATS 全局通配符订阅（#，接收所有事件）
□ App 注册表（从 manifest.json 构建能力索引）
□ 流程配置加载器（JSON 配置文件热加载）
□ 快速路由引擎（规则匹配，< 100ms）
□ 语义路由引擎（llama.cpp 推理，< 2s）
□ 动态规划引擎（多事件关联，< 5s）
□ Flow 执行引擎（顺序/并行步骤执行，HTTP 调用 App /action）
□ Context Graph 集成（读写封装）
□ 执行日志记录（可查询的任务历史）
□ Nervus 全局弹窗触发接口（POST /notify/global_popup）

验收：
  发布 media.photo.classified（food） → Arbor 快速路由到热量 App
  发布未知语义事件 → Arbor 调用 llama.cpp 推理后路由
  多事件时间窗口重叠 → Arbor 动态规划并执行
```

## Sprint 3 — 第一条完整数据流（第 5 周）

**目标：** 从手机拍照到热量 App 自动记录，全程零操作，端到端打通。

```
□ 相册扫描器服务（Python）：
    定时轮询新照片（通过 Capacitor 相册插件）
    调用 minicpm-v 视觉模型分类
    发布 media.photo.classified
□ 热量管理 App NSI 改造：
    添加 manifest.json
    实现 /intake/photo_classified
    实现 /action/analyze_meal（调用视觉模型）
    写入 Context Graph physical.*
    前端自动刷新（WebSocket 或轮询）
□ Nervus 全局弹窗实现（前端 + Arbor 触发）
□ iOS Capacitor 初步配置（相册访问权限）
□ 局域网通信封装（Capacitor → 边缘设备）

验收：
  手机拍食物照片 → 热量 App 出现自动记录 → Context Graph 更新
  Nervus 弹窗弹出（当文件进入系统时）
  全程无需用户手动操作
  端到端延迟 < 10s
```

## Sprint 4 — Memory Graph + Sense 页数据化（第 6 周）

**目标：** 系统有了真正的长期记忆，Sense 页展示真实数据。

```
□ Memory Graph 写入 API（life_events / knowledge_items）
□ pgvector 向量化 Pipeline（事件发生时自动 embedding）
□ 语义召回 API（「我上次去上海是什么时候」→ 检索 Memory Graph）
□ Context Graph 完整字段实现（对应第六部分 6.4）
□ 状态感知 App NSI 改造：
    多信号聚合推断 cognitive.load
    写入 Context Graph
    发布 context.user_state.updated
□ Sense 页前端数据化（从 Context Graph 实时读取）
□ 记忆沉淀任务（定时把 Context hot data 写入 Memory Graph）

验收：
  Sense 页展示的数据是真实 Context Graph 状态
  可以用自然语言查询 Memory Graph 并得到答案
  cognitive.load 能根据行为信号自动推断
```

## Sprint 5 — 核心 App NSI 接入（第 7–8 周，并行）

**目标：** 打通主要数据流，两个旗舰体验可用。

### 优先级 1 — 主数据流
```
□ 会议纪要 App：
    发布 meeting.recording.processed
    接收 meeting.whiteboard.detected（白板整合）
    自动生成完整报告（录音+白板）
□ 状态感知 App（Sprint 4 基础上完善）
□ 日历 App（新建）：
    订阅 context.user_state.updated
    根据 cognitive.load 生成日程调整建议
```

### 优先级 2 — 旗舰体验
```
□ 人生记忆库 App（新建）：
    订阅 media.photo.classified（旅行）
    订阅 memory.travel.moment_captured
    生成旅行日志、年度回忆录
    写入 Memory Graph life_events
□ 知识库 App（新建）：
    订阅所有 knowledge.*
    统一存储 + 语义检索 + AI 问答
    写入 Memory Graph knowledge_items
□ PDF 提取 App NSI 改造：
    完成后发布 knowledge.document.indexed
    向量化并写入 Memory Graph
```

### 优先级 3 — 生态丰富
```
□ 个人笔记 App：发布 knowledge.note.created
□ 视频转录 App：发布 knowledge.video.transcribed
□ RSS 订阅 App（新建）：发布 knowledge.article.fetched
□ 工作流 App（新建）：可视化查看 Arbor 流程配置
```

**验收：**
```
场景 A：旅行照片 → 自动归入旅行线程 → 生成旅行日志
场景 B：录音+白板 → 自动整合 → 完整会议报告
场景 C：保存文章+PDF → 关联 → 可语义问答
场景 D：状态感知 → 主动建议明日日程调整
全部场景静默完成，无需用户主动操作
```

## Sprint 6 — Capacitor iOS Shell ✅ 已完成（v1.2）

**目标：** 完整的 iOS 原生体验，端到端 MVP。

**已完成（v1.2）：**
```
✅ Capacitor 项目（ios-shell/）包裹 mobile/index.html，通过 server.url 加载远端 Nervus
✅ 5面板手势系统在真机上验证通过
✅ MainViewController.swift：
    SSL 自签名证书绕过（WKNavigationDelegate 代理模式）
    状态栏颜色跟随系统深/浅色主题（preferredStatusBarStyle）
✅ Info.plist：完整权限声明（相机/相册/麦克风/定位）
✅ Bundle ID：com.<用户名>.nervus
✅ 安装流程：npx cap sync → Xcode → Run（免费 Apple ID 可用，7天有效期）
✅ 全屏适配：viewport-fit=cover + env(safe-area-inset-top) + JS 探针
✅ 深/浅色自动切换：color-scheme meta + CSS @media + 状态栏颜色
```

**待完成（后续 Sprint）：**
```
□ 相册访问插件（PHPhotoLibrary）：监听新照片并上传到 Orin
□ 麦克风录音插件：录音传输到会议纪要 App
□ iOS Background Fetch：定期触发相册扫描
□ 本地推送通知（UserNotifications）：Arbor 完成后推送
□ 局域网自动发现（Bonjour/mDNS）：无需手动配置 IP
□ TestFlight / 付费证书（突破 7 天限制）
```

---

# 第八部分：工程规范

## 8.1 目录结构

```
nervus/
├── docker-compose.yml          # 整体服务编排
├── caddy/
│   └── Caddyfile
├── arbor-core/                 # Arbor Core 服务
│   ├── main.py
│   ├── router/                 # 快速/语义/动态路由
│   ├── executor/               # Flow 执行引擎
│   ├── flows/                  # JSON 流程配置
│   └── requirements.txt
├── nervus-sdk/                 # Python SDK
│   ├── nervus_sdk/
│   └── setup.py
├── nervus-sdk-ts/              # TypeScript SDK
│   ├── src/
│   └── package.json
├── apps/                       # 所有 App
│   ├── calorie-tracker/
│   ├── meeting-notes/
│   ├── knowledge-base/
│   ├── life-memory/
│   ├── sense/
│   └── ...（共 20 个）
├── mobile/                     # Capacitor iOS Shell
│   ├── src/                    # app-prototype.html 拆分版本
│   ├── ios/
│   └── capacitor.config.ts
└── docs/                       # 本文档
    └── Nervus_完整开发文档.md
```

## 8.2 App 开发模板

```
apps/app-name/
├── manifest.json               # NSI 能力声明
├── main.py（或 index.ts）       # App 主入口，基于 nervus-sdk
├── actions/                    # 各 Action 实现
├── models.py                   # 数据模型
├── db.py                       # SQLite 操作
├── frontend/                   # Web 前端（HTML/CSS/JS）
├── Dockerfile
└── requirements.txt
```

## 8.3 llama.cpp 部署配置

```bash
# Jetson Orin Nano 编译（CUDA 加速 + 多模态支持）
cmake -DLLAMA_CUDA=ON -DLLAMA_CURL=ON ..
make -j6

# 启动 server（常驻，多模态模型需要 --mmproj 指定视觉投影权重）
./server \
  -m /models/qwen3.5-4b-multimodal-q4_k_m.gguf \
  --mmproj /models/qwen3.5-4b-multimodal-mmproj.gguf \
  --port 8080 \
  --ctx-size 4096 \
  --n-gpu-layers 32 \
  --parallel 4 \
  --host 0.0.0.0

# 文字调用（兼容 OpenAI API 格式）
POST http://llama-cpp:8080/v1/chat/completions
Content-Type: application/json
{ "model": "qwen3.5", "messages": [...] }

# 视觉调用（图片分析，同一接口）
POST http://llama-cpp:8080/v1/chat/completions
Content-Type: application/json
{
  "model": "qwen3.5",
  "messages": [{
    "role": "user",
    "content": [
      { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } },
      { "type": "text", "text": "识别食物名称和估算热量" }
    ]
  }]
}
```

## 8.4 NATS 主题权限配置

```
# 各 App 只能发布自己声明的主题
# Arbor Core 可订阅和发布所有主题
# 通过 manifest.json 中的 publishes 字段做权限校验
```

---

# 尾声

Nervus 不是要成为最聪明的 AI。

它要成为那个让聪明真正流动起来的连接——让每一个 App 的智慧都能到达需要它的地方，让你生活里每一个值得被记住的瞬间都不会消失在孤岛里。

这个产品的灵魂，藏在一句话里：

**它从未停止存在过。**

不是工具，是伙伴。
不是功能，是生命周期。
不是你来激活它，是它一直陪着你。

把你的一生，存进一个盒子里。

---

*文档版本：v1.2 | 2026-04-26*
*配合文件：`mobile/index.html`（单文件 SPA 全部前端实现）、`ios-shell/`（Capacitor iOS 壳子）*
*Nervus · 从未停止存在的系统*
