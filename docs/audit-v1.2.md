# Nervus v1.2 代码审查与方案梳理

> 审查时间：2026-04-26  
> 审查范围：全仓库代码 + 架构方案

---

## 一、代码层面的冲突

### 1. 应用中心种子 URL 和实际部署完全对不上

`mobile/index.html` 的 `_seedApps()` 里，11 个应用全部指向 `150.158.146.192:6105~6155` 这些端口。但 `docker-compose.yml` 里根本没有这些端口——Nervus 的 14 个后端服务用的是 `8001–8015`，统一经 Caddy 反代。

**实际上存在两套"应用"概念混在一起了：**

| 类型 | 端口范围 | 访问方式 | 与 Nervus 集成 |
|------|---------|---------|--------------|
| Nervus 生态 App | 8001–8015 | 经 Caddy `/api/{app-id}/` | 有 NSI、NATS、Redis、Postgres |
| 外部 Web App | 6105、6121–6155 等 | 直接裸端口 | 无，独立部署 |

这两类在 UI 上都叫"应用中心的 App"，但背后完全不同。**目前文档和代码都没有区分这两种类型。**

---

### 2. Files 面板是唯一真正联通后端的面板

`#p-files` 用 iframe 加载 `/files/`，Caddy 路由到 file-manager（port 8015），真实可用。

其他所有面板（Home、Sense、Chat、Apps）的数据全是前端硬编码的 mock，没有调用任何后端接口。

---

### 3. Sense 面板数据是假的

`#p-sense` 展示的分数、状态、时间线全是静态 HTML。  
`apps/sense/`（port 8005）和 `apps/status-sense/`（port 8013）两个后端都写好了，但感知面板没有接任何一个。

---

### 4. Chat 面板没接 LLM

`#p-chat` 的回复是 `setTimeout 900ms` 返回固定字符串的模拟，没有调用 `llama.cpp` 服务（port 8080）。

---

### 5. `ios-shell/` 和实际 Xcode 项目存在漂移风险

真正的 Xcode 项目在 `/Users/wq/projects/webshell-app/`，`ios-shell/` 是手动 rsync 过来的副本。两边同时改动容易产生差异。

**建议**：以 `ios-shell/` 为唯一来源，Xcode 直接打开这个目录的工程，彻底去掉 `webshell-app`。

---

### 6. 两个"会议纪要"同时存在，关系不明

| 位置 | 端口 | 性质 |
|------|------|------|
| `apps/meeting-notes/` | 8002（经 Caddy） | Nervus 原生后端，接 NATS，写 Memory Graph |
| 应用中心种子"会议纪要" | 6105 | 外部独立 Web App |

用户点应用中心打开的是 6105，不是 8002。  
**待决策**：这两个是同一个东西的两种访问方式，还是两套独立实现？

---

### 7. IP 硬编码阻止了任何人部署

`mobile/index.html` 中 11 个 App URL 全是 `150.158.146.192`。  
别人 clone 仓库后不改代码无法使用，与 README 里的"给朋友部署"目标冲突。

---

## 二、方案层面的冲突

### 8. 应用中心的定位没有定义清楚

**现状**：应用中心是"书签管理器"——任何网址都能加进去，点开用 webview 打开。  
**文档里说的**：应用中心是 Nervus 生态 App 的入口，App 要实现 NSI 接口、接事件总线。

这两个定位根本不一样：

| 方向 A | 方向 B |
|--------|--------|
| 通用浏览器快捷方式 | 生态平台入口 |
| 任何网页都能加 | 只收录接了 NSI 的 App |
| 像 iOS 主屏幕 | 像 iOS 的原生设置/系统 App |

**待决策**：应用中心到底是什么？或者分两层（原生 App + 外部书签）分区展示？

---

### 9. 前端和后端的关系是断开的

14 个后端 App 全都写好了（manifest.json、NATS 订阅、API 接口），但 `mobile/index.html` 是一座孤岛，完全不知道这些 App 的存在。

正确路径应该是：前端 → 调用 Arbor Core API → Arbor 路由到对应 App。  
**但现在没有任何一条数据流从前端走到 Arbor。**

Arbor Core 写得很完整，却是整个系统里最孤独的服务。

---

## 三、各组件实际完成状态

| 组件 | 代码完成度 | 与系统联通度 | 说明 |
|------|-----------|------------|------|
| Arbor Core | ✅ 完整 | ❌ 未接前端 | FastRouter/SemanticRouter/DynamicRouter 都实现了 |
| 14 个后端 App | ✅ 完整 | ❌ 未接前端 | 各有 manifest.json、NSI 接口、NATS 订阅 |
| nervus-sdk (Python) | ✅ 完整 | ✅ 被各 App 使用 | |
| nervus-sdk-ts (TS) | ✅ 完整 | ❌ 无 TS App | SDK 写好了但没有任何 App 使用它 |
| NATS + Redis + Postgres | ✅ 完整 | ✅ 基础设施就绪 | |
| Whisper | ✅ 完整 | ❌ 未被前端调用 | |
| llama.cpp | ⚙️ 外部依赖 | ❌ Chat 面板未接 | 不在仓库里，独立部署 |
| mobile/index.html | ✅ UI 完整 | ⚠️ 仅 Files 面板联通 | 其余面板全是 mock |
| iOS Shell | ✅ 基础壳完整 | ⚠️ 无原生插件 | 相册/麦克风/推送未实现 |
| file-manager | ✅ 完整 | ✅ 已联通 | 唯一真正端到端的面板 |
| Caddy | ✅ 完整 | ✅ 路由配置正确 | |

---

## 四、建议调整优先级

### P0 — 需要先做决策，再动代码

**① 定义应用中心的两种 App 类型**  
建议：在 UI 上区分"Nervus App"（有 NSI 集成）和"外部书签"两类，或分区展示。在 `_seedApps()` 的数据结构里加一个 `type: 'nervus' | 'external'` 字段。

**② 决定 6105~6155 这些外部 App 的归宿**  
这些服务是你手动部署在 Orin 上的，仓库里没有它们的代码。  
选项 A：把这些 App 的代码也纳入仓库（`apps/meeting-notes-ui/` 等）  
选项 B：保持外部，但在 README 里说明，种子数据改成占位符而非硬编码 IP

---

### P1 — 打通第一条真实数据流

**③ 感知面板接真实数据**  
最小改动：前端 `fetch('/api/sense/state')` 替换掉 mock 数据。  
一旦这条路通了，整个架构就活了，Arbor 的价值才能体现。

**④ Chat 面板接 LLM**  
`fetch('/api/chat', { method: 'POST', body: JSON.stringify({ message }) })`  
或直接调 `https://<host>/v1/chat/completions`（llama.cpp OpenAI 兼容接口）。

---

### P2 — 清理工程债务

**⑤ 统一 iOS 工程路径**  
删掉 `webshell-app`，Xcode 直接用 `nervus-core-linkbox/ios-shell/`。

**⑥ 把 IP 从代码里移出去**  
`mobile/index.html` 启动时读取 `window.NERVUS_HOST` 或从 `/config.json` 拉取，Caddy 提供这个配置接口。种子 App 的外部 URL 走同样机制。

**⑦ 明确 file-manager 前后端关系**  
`apps/file-manager/frontend/` 是 Vue 3 项目但没有集成进构建流程。  
要么把 Vue 打包产物放进 Caddy 的静态目录，要么删掉前端目录改成纯后端。

---

### P3 — 长期

**⑧ TypeScript SDK 找到用武之地**  
`nervus-sdk-ts` 写得完整但没有任何 App 使用。下一个新 App 用 TypeScript 实现，验证 SDK 可用性。

**⑨ 补充测试**  
目前零测试覆盖。至少给 Arbor Core 的路由逻辑加 pytest 单元测试，防止后续改动破坏核心链路。

---

*本文档由代码审查自动生成，记录 v1.2 时间点的状态。*  
*下次审查建议在 P0/P1 完成后进行。*
