# AutoPaper

中文 | [English](README.md)

AutoPaper 是一个“优化论文”的闭环：外部 coding agent 负责改写 `paper.tex`，固定的多模型 reviewer 负责打分。

它不是自带 agent runtime 的产品。你提供 Claude Code、Codex 或其他 coding agent；这个仓库提供 reviewer、运行流程和约束规则。

## 工作方式

1. 在当前仓库启动 agent，并让它先阅读 `program.md`。
2. agent 先执行 `uv run reviewer.py --dry-run`，确认 reviewer 可用，然后开始修改 `paper.tex`。
3. `reviewer.py` 对 LaTeX 源稿打分，agent 根据结果决定保留还是回退，然后继续下一轮。

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 编辑 reviewer.py 顶部的 REVIEWERS 列表

# 3. 用你的论文替换 paper.tex
# results/ 是可选目录，可用于放笔记、人工总结或原始材料；没有这些内容时可以留空

# 4. 在当前目录启动 Claude Code 或其他 coding agent
# 示例提示词：
# Read program.md and start optimizing the paper in paper.tex.
```

## Agent 会做什么

- 在第一次正式评分前先运行 `uv run reviewer.py --dry-run`
- 用 git 和 `results.tsv` 保存每轮历史
- 用 `.autopaper/working_memory.md` 维护简短运行记忆
- 遇到目标、事实、实验细节或引用信息不确定时，先问人，不猜
- 以第一性原理为主，先修问题定义、贡献链路、证据和最薄弱论证，再修文风
- 对参考文献采取保守策略：复用仓库中已验证条目，不自行编造 citation 或 bibliography 事实

## 审稿模型配置

通过编辑 `reviewer.py` 顶部的 `REVIEWERS` 列表来配置模型。

```python
REVIEWERS = [
    {
        "model": "gpt-4o",
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1",
    },
    {
        "model": "anthropic/claude-sonnet-4-6",
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "base_url": os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1",
    },
    {
        "model": "gemini/gemini-2.0-flash",
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "base_url": os.getenv("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai",
    },
]
```

每个 reviewer 都使用同一种兼容格式：`model`、`api_key`、`base_url`。如果接入其他服务，保持相同结构并把 `base_url` 指向对应接口即可。

```python
{
    "model": "your-model-name",
    "api_key": os.getenv("PROVIDER_API_KEY", ""),
    "base_url": "https://your-endpoint/v1",
}
```

每次正式评分至少需要 `MIN_QUORUM` 个 reviewer 成功返回结果。

## 停止条件

满足以下任一条件时，优化循环会停止：

- `review_score` 达到 `TARGET_SCORE`
- 连续 `CONVERGENCE_ROUNDS` 轮的提升低于设定阈值
- 你手动停止 agent

完整运行规则见 `program.md`。

## 仓库结构

```text
autopaper/
├── .autopaper/
│   └── working_memory.md
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

## 边界说明

- `reviewer.py` 评审的是 `paper.tex` 的 LaTeX 源文本，不是编译后的 PDF。
- 更高的 `review_score` 有参考价值，但它仍然只是代理指标，不能替代真实同行评审。
- 不要把 API key 或其他密钥直接提交到仓库里。
