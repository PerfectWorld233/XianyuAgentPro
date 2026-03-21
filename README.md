# 🚀 Xianyu AutoAgent - 智能闲鱼客服机器人系统

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/) [![LLM Powered](https://img.shields.io/badge/LLM-powered-FF6F61)](https://platform.openai.com/)

专为闲鱼平台打造的AI值守解决方案，实现闲鱼平台7×24小时自动化值守，支持多专家协同决策、智能议价和上下文感知对话。 


## 🌟 核心特性

### 智能对话引擎
| 功能模块   | 技术实现            | 关键特性                                                     |
| ---------- | ------------------- | ------------------------------------------------------------ |
| 上下文感知 | 会话历史存储        | 轻量级对话记忆管理，完整对话历史作为LLM上下文输入            |
| 专家路由   | LLM prompt+规则路由 | 基于提示工程的意图识别 → 专家Agent动态分发，支持议价/技术/客服多场景切换 |

### 业务功能矩阵
| 模块     | 已实现                        | 规划中                       |
| -------- | ----------------------------- | ---------------------------- |
| 核心引擎 | ✅ LLM自动回复<br>✅ 上下文管理 | 🔄 情感分析增强               |
| 议价系统 | ✅ 阶梯降价策略                | 🔄 市场比价功能               |
| 技术支持 | ✅ 网络搜索整合                | 🔄 RAG知识库增强              |
| 运维监控 | ✅ 基础日志                    | 🔄 钉钉集成<br>🔄  Web管理界面 |

## 🎨效果图
<div align="center">
  <img src="./images/demo1.png" width="600" alt="客服">
  <br>
  <em>图1: 客服随叫随到</em>
</div>


<div align="center">
  <img src="./images/demo2.png" width="600" alt="议价专家">
  <br>
  <em>图2: 阶梯式议价</em>
</div>

<div align="center">
  <img src="./images/demo3.png" width="600" alt="技术专家"> 
  <br>
  <em>图3: 技术专家上场</em>
</div>

<div align="center">
  <img src="./images/log.png" width="600" alt="后台log"> 
  <br>
  <em>图4: 后台log</em>
</div>


## 🚴 快速开始

小白请直接查看[保姆级教学文档](https://my.feishu.cn/wiki/JtkBwkI9GiokZikVdyNceEfZncE)

---

## 🖥️ 桌面应用（Electron + Vue 3）

### 环境要求

| 工具 | 版本要求 |
|------|---------|
| Python | 3.8+ |
| Node.js | 18+ |
| npm | 9+ |

### 一、首次安装

```bash
# 1. 克隆仓库
git clone https://github.com/shaxiu/XianyuAutoAgent.git
cd XianyuAutoAgent

# 2. 安装 Python 依赖
pip install -r python/requirements.txt

# 3. 安装 Playwright 浏览器（扫码登录功能所需）
playwright install chromium

# 4. 安装 Electron 依赖（含 better-sqlite3 原生重编译）
cd electron
npm install
```

### 二、本地开发运行

```bash
# 在 electron/ 目录下启动开发模式
# 同时启动 Vite 开发服务器 + Electron 窗口，支持热更新
cd electron
npm run dev
```

> 开发模式下 Electron 会直接用 `python bridge.py` 启动 Python 后端，无需打包。

### 三、配置

首次启动后，在应用的「设置」页面填写：

| 配置项 | 说明 |
|--------|------|
| **API Key** | LLM 平台 API Key（通义千问等） |
| **Cookie** | 闲鱼网页端 Cookie，或直接点击「扫码登录」自动获取 |
| 模型地址 | 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 模型名称 | 默认 `qwen-max` |

**扫码登录（推荐）**：点击控制台页面的「扫码登录」按钮，会自动弹出 Chromium 浏览器，扫码后 Cookie 自动写入，无需手动复制。

### 四、打包发布（Windows）

#### 方式 A：一键全量打包

```bat
scripts\build-all.bat
```

依次执行以下四步，完成后产物位于 `build/` 目录：

```
build/
├── python-dist/bridge/          # PyInstaller 打包的 Python 可执行文件
├── electron-dist/win-unpacked/  # Electron 解包目录
└── installer-output/            # Inno Setup 生成的安装包 .exe
```

> Inno Setup 需单独安装：[Inno Setup 6](https://jrsoftware.org/isdl.php)，安装后脚本自动检测路径。

#### 方式 B：分步打包

```bat
# Step 1：PyInstaller 打包 Python bridge
scripts\build-python.bat

# Step 2：Vite 构建前端
cd electron
npm run build:renderer

# Step 3：electron-builder 打包
npm run build:electron

# Step 4：Inno Setup 制作安装包（需已安装 Inno Setup 6）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss
```

## 🤝 参与贡献

欢迎通过 Issue 提交建议或 PR 贡献代码

## 🛡 注意事项

⚠️ 注意：**本项目仅供学习与交流，如有侵权联系作者删除。**

鉴于项目的特殊性，开发团队可能在任何时间**停止更新**或**删除项目**。


