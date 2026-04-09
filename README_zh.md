# AutoPaper

中文 | [English](README.md)

AutoPaper 是一个极简框架，用固定的多模型审稿器驱动 AI 代理迭代优化 LaTeX 论文。

代理负责修改草稿，评审器负责打分，整个循环围绕单一指标 `review_score` 展开。

## 为什么是 AutoPaper

- 单一编辑目标。代理只改 `paper.tex`。
- 固定评审基线。`reviewer.py` 在实验过程中保持不变。
- 多模型独立打分。多个 LLM 对同一稿件分别评审。
- 简单的优化闭环。修改、评审、保留或回退，然后继续。

## 工作方式

AutoPaper 主要围绕三个文件运转：

- `paper.tex`：代理编辑的论文草稿
- `reviewer.py`：负责打分的评审 harness
- `program.md`：代理实验循环的操作说明

评审器从四个维度打分：

- `soundness`
- `clarity`
- `novelty`
- `significance`

每个审稿模型返回 1 到 10 的整数分。AutoPaper 再对多位审稿人的结果取平均并计算加权 `review_score`，所以最终聚合输出可以是小数。

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 编辑 reviewer.py 顶部的 REVIEWERS 列表来配置审稿模型

# 3. 用你的论文替换 paper.tex

# 4. 验证审稿环境
uv run reviewer.py

# 5. 在当前目录启动 Claude Code 或其他 coding agent
# 示例提示词：
# Read program.md and kick off a new experiment.
```

`uv run reviewer.py` 只负责运行评审 harness。要执行完整的自动优化循环，仍然需要 Claude Code、Codex 这类外部 agent 读取 `program.md`、修改 `paper.tex` 并决定每轮是否保留改动。

## 审稿模型配置

通过编辑 `reviewer.py` 顶部的 `REVIEWERS` 列表来配置模型。

```python
REVIEWERS = [
    {
        "model": "gpt-4o",
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": None,
    },
    {
        "model": "claude-sonnet-4-6",
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "base_url": None,
    },
    {
        "model": "gemini/gemini-2.0-flash",
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "base_url": None,
    },
]
```

按提供方分类的模板如下：

```python
# OpenAI
{
    "model": "gpt-4o",
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "base_url": None,
}

# Anthropic
{
    "model": "claude-sonnet-4-6",
    "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    "base_url": None,
}

# Gemini
{
    "model": "gemini/gemini-2.0-flash",
    "api_key": os.getenv("GEMINI_API_KEY", ""),
    "base_url": None,
}
```

如果使用 OpenAI 兼容接口，结构保持一致，同时设置 `api_key` 和 `base_url`：

```python
{
    "model": "your-model-name",
    "api_key": os.getenv("PROVIDER_API_KEY", ""),
    "base_url": "https://your-endpoint/v1",
}
```

每次运行至少需要 `MIN_QUORUM` 个审稿模型成功返回结果。

## 仓库结构

```text
autopaper/
├── paper.tex
├── reviewer.py
├── program.md
├── pyproject.toml
├── uv.lock
├── results/
│   └── raw/
├── README.md
└── README_zh.md
```

## 说明

- `reviewer.py` 在正式评审前会先做连通性 preflight 检查。
- `results/` 可以存放实验记录或原始材料，也可以保持为空。
- 不要把 API key 或其他密钥直接提交到仓库里。
- 更高的 `review_score` 有参考价值，但它仍然只是代理指标，不能替代真实同行评审。
