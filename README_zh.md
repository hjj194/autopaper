# AutoPaper

中文 | [English](README.md)

自主学术论文写作优化系统，灵感来自 [autoresearch](https://github.com/karpathy/autoresearch)。

## 这个仓库做什么

AutoPaper 用来让 AI 代理迭代优化一篇 LaTeX 论文草稿。

基本循环很简单：
1. 修改 `paper.tex`
2. 运行 `reviewer.py`
3. 读取当前最低分维度和总分
4. 决定保留还是丢弃这次修改
5. 重复执行

评审器会用多个 LLM 从四个维度打分：
- soundness
- clarity
- novelty
- significance

最后汇总成单一指标 `review_score`。

## 最小发布目录

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

## 核心文件

- `paper.tex`：代理唯一应该修改的文件
- `reviewer.py`：固定评审 harness
- `program.md`：代理实验循环说明

## 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- 至少 2 个可用的 LLM 审稿模型

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 在 reviewer.py 中配置审稿模型
# API key 建议通过环境变量传入

# 3. 用你的论文替换 paper.tex

# 4. 跑一次基线评审
uv run reviewer.py

# 5. 在当前目录启动 AI 代理
# 示例提示词：
# Read program.md and kick off a new experiment.
```

## 审稿模型配置

编辑 `reviewer.py` 顶部的 `REVIEWERS` 列表。

示例：

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

如果使用 OpenAI 兼容接口，同时配置 `api_key` 和 `base_url` 即可。

## 说明

- `reviewer.py` 在正式评审前会做连通性 preflight 检查。
- 至少要有 `MIN_QUORUM` 个模型成功返回结果。
- `results/` 可以放人工总结或原始实验材料，也可以先空着。
- 不要把密钥直接提交进 `reviewer.py`。
