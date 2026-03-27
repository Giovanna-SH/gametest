# 🎮 LLM 游戏代码生成评测 — A 组 (System Prompt)

## 项目说明

用 [0xfurai/claude-code-subagents](https://github.com/0xfurai/claude-code-subagents) 提示词库作为 System Prompt，
分别驱动 **DeepSeek Chat** 和 **Gemini 2.5 Flash** 生成小游戏代码，自动采集 Token 消耗、代码行数、耗时等指标，
最终输出 Excel 评测报告。

---

## 📁 项目结构

```
benchmark/
├── config/
│   ├── tasks.json          # 评测任务（5 个游戏）
│   └── models.json         # 模型 & Agent 配置
├── prompts/                # Agent 提示词文件（.md）
│   ├── javascript-expert.md
│   ├── html-expert.md
│   └── css-expert.md
├── runner/
│   ├── evaluator.py        # 🔥 主入口：评测引擎
│   ├── api_client.py       # DeepSeek / Gemini 统一 API 客户端
│   ├── code_extractor.py   # 从回复中提取代码 + 代码度量
│   ├── screenshotter.py    # Playwright 自动截图
│   └── report.py           # 生成 Excel 评测报告
├── outputs/                # 产出目录
│   ├── code/               # 生成的游戏 HTML
│   ├── screenshots/        # 运行截图
│   ├── benchmark_results.xlsx
│   └── benchmark_results.json
├── requirements.txt
└── README.md
```

---

## 🚀 操作步骤（从零开始）

### 第 1 步：环境准备

```bash
# Python 3.10+ 推荐
python --version

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器（用于截图）
playwright install chromium
```

### 第 2 步：获取 API Key

#### DeepSeek
1. 访问 https://platform.deepseek.com/
2. 注册 → 进入 API Keys 页面 → 创建 Key
3. 记录 Key（以 `sk-` 开头）

#### Gemini
1. 访问 https://aistudio.google.com/
2. 登录 Google 账号 → 点击 "Get API key" → 创建 Key
3. 记录 Key（以 `AIza` 开头）

### 第 3 步：设置环境变量

```bash
# Linux / macOS
export DEEPSEEK_API_KEY="sk-你的key"
export GEMINI_API_KEY="AIza你的key"

# Windows PowerShell
$env:DEEPSEEK_API_KEY="sk-你的key"
$env:GEMINI_API_KEY="AIza你的key"
```

### 第 4 步：下载真实的 Agent 提示词（可选增强）

项目已内置精简版提示词。如果你想用 GitHub 上的原版：

```bash
# 克隆原始仓库
git clone https://github.com/0xfurai/claude-code-subagents.git /tmp/subagents

# 复制你需要的 agent 文件到 prompts 目录
cp /tmp/subagents/agents/javascript-expert.md prompts/
cp /tmp/subagents/agents/react-expert.md prompts/
# ...按需复制更多
```

然后编辑 `config/models.json` 里的 `agents.prompt_files` 字段指向你要用的文件。

### 第 5 步：验证配置（Dry Run）

```bash
cd benchmark
python runner/evaluator.py --dry-run
```

输出应类似：
```
════════════════════════════════════════════════════════════
DRY RUN — Configuration Summary
════════════════════════════════════════════════════════════
Models:  ['deepseek-chat', 'gemini-2.5-flash']
Tasks:   ['Snake Game', '2048 Game', 'Tetris', 'Minesweeper', 'Flappy Bird']
Agent:   JavaScript + HTML + CSS Expert
Mode:    Single-turn
System prompt length: 2847 chars
...
```

### 第 6 步：运行评测

```bash
# ── 完整评测（2 模型 × 5 任务 = 10 次 API 调用）──
python runner/evaluator.py

# ── 只测一个模型、一个任务（调试用）──
python runner/evaluator.py --model deepseek-chat --task 0

# ── 启用多轮自我修复 ──
python runner/evaluator.py --multi-turn

# ── 跳过截图（没装 Playwright 时）──
python runner/evaluator.py --no-screenshot
```

### 第 7 步：查看结果

评测完成后，在 `outputs/` 目录下你会得到：

| 文件 | 说明 |
|------|------|
| `benchmark_results.xlsx` | Excel 报告（和你截图格式一致） |
| `benchmark_results.json` | JSON 原始数据 |
| `code/deepseek-chat/0_Snake_Game.html` | DeepSeek 生成的 Snake 游戏 |
| `code/gemini-2.5-flash/0_Snake_Game.html` | Gemini 生成的 Snake 游戏 |
| `screenshots/*.png` | 各游戏运行截图 |

可以直接用浏览器打开 `code/` 下的 HTML 文件来玩生成的游戏。

---

## ⚙️ 配置说明

### models.json 关键字段

```jsonc
{
  "models": [
    {
      "id": "deepseek-chat",           // 显示在报告中的名称
      "name": "deepseek-chat",          // API 实际的 model 参数
      "provider": "deepseek",           // 决定用哪个 Client
      "base_url": "https://api.deepseek.com/v1",
      "api_key_env": "DEEPSEEK_API_KEY", // 读取哪个环境变量
      "max_tokens": 16384,              // 最大输出 token
      "temperature": 0.0                // 0 = 确定性输出，可复现
    }
  ],
  "agents": [
    {
      "id": "javascript-html-css",
      "name": "JavaScript + HTML + CSS Expert",
      "prompt_files": ["javascript-expert.md", "html-expert.md", "css-expert.md"],
      // ↑ 这些文件会按顺序拼接成一个 system prompt
    }
  ],
  "max_iterations": 5  // 多轮模式最大修复次数
}
```

### tasks.json 自定义任务

```json
[
  {
    "id": 5,
    "name": "Breakout",
    "prompt": "Create a Breakout/Arkanoid game for the web. Requirements: single HTML file..."
  }
]
```

---

## 📊 产出的 Excel 列说明

| 列 | 数据来源 |
|----|----------|
| 测评ID | tasks.json 的 id |
| 任务名称 | tasks.json 的 name |
| 任务描述 | tasks.json 的 prompt（截断） |
| 语言模型 | models.json 的 id |
| 涉及Agent | agents 的 name |
| 对话轮次 | API 调用次数（单轮=1，多轮=1+修复次数） |
| AI提问消耗Token | API response → usage.prompt_tokens（累计） |
| AI回答消耗Token | API response → usage.completion_tokens（累计） |
| 总消耗Token | 提问+回答 之和 |
| 代码总行数 | 提取出的代码 `\n` 计数 |
| 代码文件数 | 含 style/script 的逻辑文件数 |
| 自我迭代次数 | 多轮模式下的修复轮数（单轮模式=0） |
| 总耗时 | 从第一次调用到最后一次调用的秒数 |
| 运行结果截图 | Playwright 截图嵌入 Excel |

---

## 💡 Tips

- **费用预估**：每次完整评测约 10 次 API 调用，DeepSeek 很便宜（约 ¥0.5），Gemini 2.5 Flash 有免费额度
- **temperature=0**：确保结果可复现，每次运行相同输入得到相同输出
- **断点续跑**：引擎每完成一个任务就保存 `results_interim.json`，崩溃后可以手动恢复
- **Agent 组合实验**：修改 models.json 的 prompt_files，试不同 agent 组合看效果差异
