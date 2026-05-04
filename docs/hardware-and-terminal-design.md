# Nervus v2 设计思考：硬件选型 + 终端优先架构

> 本文档记录了 Nervus 从手机 App 向独立 AI 硬件设备演进过程中的核心设计决策。

---

## 一、背景：第一代 AI 硬件为什么失败

以 Rabbit r1 为代表的第一代 AI 硬件设备存在根本性缺陷：

| 设备 | 核心问题 |
|------|----------|
| Rabbit r1 | 底层是 Android + 一个 Launcher APK，并非真正的 AI OS |
| Humane AI Pin | 无屏幕、延迟高、缺乏自主执行能力 |

**Rabbit r1 的本质**：联发科 MT6765（2018 年芯片）+ Android AOSP + 全屏 APK。
有人将该 APK 安装到普通安卓手机上，可完整复现 r1 的全部功能，说明其硬件与软件并未真正整合。

**共同症结**：这些设备只是"更好的语音助手"，不是"能替你做事的 Agent"。

---

## 二、芯片选型讨论

### 为什么不用 RK3576？

RK3576 有 6 TOPS NPU，但 **LLM 推理是内存带宽瓶颈，而非算力瓶颈**：

- 每生成一个 token，需将整个模型权重从内存读一遍
- RK3576 内存带宽约 50 GB/s，实际可用模型上限约 0.5B~1B
- RKNN SDK 针对 CNN/视觉模型设计，Transformer 算子支持不完整
- 4B 模型（Q4 约 2.5GB 权重）需要 ~25 GB/s 带宽，远超其能力

**结论**：RK3576 NPU 在 LLM 推理场景基本不可用，上限 0.5B 勉强。

### 真正能跑 LLM 的芯片

| 芯片 | 内存带宽 | 可用模型上限 |
|------|---------|------------|
| 骁龙 8 Gen 3 | ~77 GB/s | 7B 流畅 |
| 骁龙 8 Elite | ~120 GB/s | 13B 可用 |
| Apple M 系列 | 100~400 GB/s | 30B+ |

但这些芯片授权门槛高、功耗大、成本接近手机级别，不适合初期原型。

### 最终选型：Allwinner H618

**规格**：4核 Cortex-A53，28nm，Mali-G31 GPU，最高 4GB LPDDR4，无 NPU

**选择理由**：

1. **推理全部放云端**（DeepSeek / OpenAI API），本地不需要 AI 算力
2. 去掉前端 UI 层后，内存占用约 1.3GB，4GB 足够
3. Linux 支持成熟（Orange Pi Zero 3 等设备社区活跃）
4. 成本极低，适合原型验证

**内存估算（精简配置）**：

```
Arbor Core           ~200MB
PostgreSQL + pgvector ~300MB
Redis + NATS         ~110MB
核心 App 容器         ~400MB
系统底层              ~300MB
──────────────────────────
合计                  ~1.3GB   （4GB 中还剩约 2.7GB）
```

**语音识别**：不在本地跑 Whisper，改用**讯飞云端 ASR**。中文准确率更高，延迟更低，且节省约 800MB 内存。

---

## 三、云端 + 本地的职责划分

```
本地（H618 设备）：
  - 意图路由（Arbor Core 三级路由引擎）
  - 上下文持久化（PostgreSQL + Redis）
  - 传感器接入（摄像头、麦克风）
  - 隐私数据加密存储

云端：
  - LLM 推理（70B 级别模型）
  - Agent 规划与工具调用
  - 语音识别（讯飞 ASR）
```

设备的核心价值不是算力，而是**本地路由、持久记忆、隐私边界**。

---

## 四、终端优先架构（Terminal-First）

### 核心洞察

Claude Code、Aider 等真正有生产力的 AI 工具，都活在终端里。

```
传统 OS：管理硬件资源，给 App 提供运行环境
Agent OS：管理意图和任务，给 Agent 提供执行环境
```

Nervus 的后端（Arbor Core + 所有 App）本身已完全无状态地运行于 NATS + HTTP 之上，前端只是 Caddy 代理的一个静态 HTML 文件，**完全可以去掉**。

### 为什么终端比前端更适合 Agent OS

| 维度 | 前端 Web UI | 终端 TUI |
|------|------------|---------|
| H618 内存占用 | ~400-600MB（Chromium） | ~50MB |
| 启动速度 | 慢 | 极快 |
| SSH 远程访问 | 需要额外配置 | 原生支持 |
| 后端耦合 | 需要维护 API 契约 | 直接连 NATS/HTTP |
| 硬件适配 | 需要浏览器渲染引擎 | 任何终端均可 |

**前端不是核心，而是可选插件**。后期可以在 TUI 之上叠加 Web UI，但 Agent 逻辑与之无关。

---

## 五、nervus-cli：Textual TUI 原型

### 设计目标

适配 3.5 寸 480×320 横屏（约 60列 × 20行），提供完整的 Agent 交互体验。

### 界面布局

```
┌ Nervus ●  14:30 ─────────────────────────────────────────┐
│                                                           │
│  ∷ Nervus 已启动                                         │
│  14:31 你: 帮我设置明天10点的会议提醒                    │
│  14:31 reminder: 已创建提醒：明天 10:00 会议             │
│                                                           │
├───────────────────────────────────────────────────────────┤
│  输入消息...                                        [V]   │
│  V 语音  S 状态  A 应用  L 日志  ? 帮助  Q 退出          │
└───────────────────────────────────────────────────────────┘
```

### 文件结构

```
nervus-cli/
├── .env.example    # 配置模板
├── requirements.txt
├── config.py       # 环境变量配置
├── client.py       # Arbor Core HTTP + NATS 客户端
├── voice.py        # 讯飞实时 ASR（WebSocket）
└── app.py          # Textual 主界面
```

### 消息流

```
用户输入（文字/语音）
    ↓
NATS publish: system.user.input
    ↓
Arbor Core 三级路由（fast → semantic → dynamic）
    ↓
对应 App 处理
    ↓
NATS / HTTP 通知回显到终端
```

### 快捷键

| 按键 | 功能 |
|------|------|
| Ctrl+V / F1 | 语音输入（讯飞 ASR） |
| Ctrl+S / F2 | 系统状态 |
| Ctrl+A / F3 | 应用列表 |
| Ctrl+L / F4 | 执行日志 |
| Ctrl+Q | 退出 |

H618 上的物理按键可以映射为上述任意键码。

### 运行

```bash
cd nervus-cli
cp .env.example .env   # 填入讯飞 key 和 Arbor URL
pip install -r requirements.txt
python app.py
```

---

## 六、操作系统选型

### 首选：Armbian Bookworm（Debian 12）Server 版

```
https://www.armbian.com/orange-pi-zero3/
→ 选 Minimal / CLI（不带桌面）
→ 基于 Debian 12 Bookworm
```

| 维度 | 说明 |
|------|------|
| H618 硬件支持 | Armbian 专门维护 H618 内核补丁，GPIO、音频、USB 开箱即用 |
| 内存占用 | Minimal 镜像空闲内存约 150MB，比官方镜像省 ~100MB |
| Docker 支持 | 内核 >= 6.1，cgroups v2 完整支持，Docker 装完即用 |
| 电源管理 | 针对 Cortex-A53 做了 cpufreq 调优，长期运行更稳定 |
| 社区活跃度 | H618 板子问题在 Armbian 论坛基本都有答案 |

### 不推荐的选项

| 选项 | 原因 |
|------|------|
| Orange Pi 官方 OS | 基于旧内核，维护频率低，预装软件冗余 |
| Ubuntu Desktop | 桌面环境白白吃掉 ~600MB，对无头设备完全没用 |
| Alpine Linux | musl libc 在 Docker 容器内兼容性问题多，排查麻烦 |

### 装好后的初始化步骤

```bash
# 1. 禁用不需要的服务（省内存）
systemctl disable bluetooth avahi-daemon
systemctl disable apt-daily.timer apt-daily-upgrade.timer

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# 3. 安装 nervus-cli 依赖
apt install python3-pip portaudio19-dev   # sounddevice 需要 portaudio

# 4. 确认麦克风被识别
apt install alsa-utils
arecord -l
```

---

## 七、后续路线图

| 阶段 | 目标 |
|------|------|
| 当前 | nervus-cli TUI 原型，在现有机器上验证体验 |
| 近期 | 在 H618 设备上跑精简版 docker-compose + nervus-cli |
| 中期 | 物理按键 GPIO 接入，语音唤醒，设备封装 |
| 远期 | 定制外壳，量产，Web UI 作为可选插件 |

---

## 七、核心结论

> **不要做"更好看的语音助手"，要做"放在口袋里的、能自主完成任务的 Agent 终端"。**

Nervus 的真正壁垒是 **Arbor Core 的路由引擎 + 持久上下文记忆 + 可扩展 App 生态**，硬件只是载体。

终端优先不是退步，而是回归本质：Agent 不需要漂亮的 GUI，它需要可靠的执行能力。
