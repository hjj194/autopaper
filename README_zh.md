# AutoPaper

中文 | [English](README.md)

学术论文在投稿前往往经历几十轮修改。你改了一段，重新通读全文，琢磨措辞是更好了还是更差了，然后重复。这个过程很慢，而且自我审视总有盲区。

AutoPaper 把这个过程变成一个紧凑的自动循环。AI coding agent 改写你的 `paper.tex`，一组 LLM 从四个维度给稿件打分，没有提升的改动自动回退，循环继续——一轮接一轮——直到分数收敛或达到目标。

你提供 agent（Claude Code、Codex 或任何能编辑文件、跑命令的工具）。这个仓库提供评审引擎、运行协议和约束规则。

## 工作方式

```
          ┌──── 编辑 paper.tex ────┐
          │                        ▼
      Agent                   reviewer.py
   (Claude Code,              (GPT-4o +
    Codex 等)                   Claude +
          ▲                    Gemini)
          │                        │
          └──── 分数 + 反馈 ───────┘
```

每一轮，agent 读取上次评审结果，找到最弱的评分维度，做一次针对性修改。提交改动，跑评审，然后决策：

- **分数提升了？** 保留 commit，继续下一轮。
- **分数下降了？** 用 `git reset --hard HEAD~1` 回退。
- **变化太小难以判断？** 跑一轮确认评审来打破平局。

每次尝试都记录到 `results.tsv`，包括 commit hash、分数、费用和改了什么。git 历史提供完整的审计轨迹——你可以 diff 任意两轮来查看具体改动。

## 评审机制

评审从四个维度打分，每项 1–10 分（整数）：

| 维度 | 权重 | 评估内容 |
|------|------|---------|
| **Soundness** | 35% | 技术正确性、方法论和实验的有效性 |
| **Clarity** | 30% | 写作质量、结构、可理解性 |
| **Novelty** | 20% | 相对于已有工作的原创性 |
| **Significance** | 15% | 重要性和对领域的潜在影响 |

三个不同的 LLM 独立评审，然后取平均分。加权求和得到 `review_score`，最低维度成为 `weakest_dim`——agent 下一轮重点攻克的方向。

一次典型的评审输出：

```
---
review_score:   6.580
soundness:      7.3
clarity:        5.7
novelty:        6.5
significance:   7.0
weakest_dim:    clarity
cost_usd:       0.91
duration_sec:   48
reviewers_ok:   3/3
---
reviewer:gpt-5.4:  soundness=8 clarity=5 novelty=7 significance=7
reviewer:claude-sonnet-4-6:  soundness=7 clarity=6 novelty=6 significance=7
reviewer:gemini-2.0-flash:  soundness=7 clarity=6 novelty=7 significance=7
max_spread_dim:   soundness
max_spread_val:   1.0
---
```

逐模型拆分让你看到它们什么时候一致、什么时候分歧。`max_spread_val` 标记分歧最大的维度——数值大的时候说明该维度分数噪声较高，agent 会更谨慎地对待。

## 一次运行的样子

Agent 把每轮结果记录到 `results.tsv`：

```
commit   review_score  cost_usd  status   weakest_dim  description
a1b2c3d  6.120         0.82      keep     clarity      baseline
b2c3d4e  6.580         0.91      keep     clarity      sharpen thesis statement and contributions list
c3d4e5f  6.510         0.88      discard  novelty      rewrote abstract — no improvement
d4e5f6g  6.890         0.85      keep     novelty      add explicit comparison to prior work in intro
e5f6g7h  7.150         0.79      keep     novelty      expand methodology with formal problem statement
f6g7h8i  7.130         0.83      discard  clarity      tighten related work — marginal regression
g7h8i9j  7.340         0.90      keep     clarity      restructure experiments section
```

循环在以下任一条件满足时停止：`review_score` 达到目标（默认 8.5）、连续多轮提升低于阈值、或你手动中断。

## 快速开始

```bash
uv sync                                          # 安装依赖
cp autopaper.example.toml autopaper.toml          # 复制配置模板
# 在 autopaper.toml 中填入你的 API key

# 用你的论文替换 paper.tex，然后启动 agent：
# "Read program.md and start optimizing the paper."
```

## 配置

编辑 `autopaper.toml` 设置审稿模型、目标会议和评分权重：

```toml
[reviewer]
venue = "NeurIPS"
min_quorum = 2
temperature = 0.0

[weights]
soundness = 0.35
clarity = 0.30
novelty = 0.20
significance = 0.15

[[models]]
model = "gpt-5.4"
api_key = "sk-..."
base_url = "https://api.openai.com/v1"

[[models]]
model = "anthropic/claude-sonnet-4-6"
api_key = "sk-ant-..."
base_url = "https://api.anthropic.com/v1"

[[models]]
model = "gemini/gemini-2.0-flash"
api_key = "gai-..."
base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
```

`[[models]]` 可以加任意多个——[litellm](https://docs.litellm.ai/docs/providers) 支持的模型都能用。每次评分至少需要 `min_quorum` 个成功返回。密钥写在 TOML 文件里（已 gitignore），也可以留空回退到环境变量。

完整模板见 `autopaper.example.toml`。

## Agent 做什么

Agent 遵循 `program.md` 中的详细协议运行整个循环：

- 评分、找到最弱维度、做针对性修改。
- 每轮只提交一个 commit。有提升就保留，没提升就回退。
- 遇到模糊的东西会停下来问你——缺引用、不确定的数据、含糊的 claim。
- 先修论证结构和证据链，再管文风打磨。
- 绝不编造参考文献。需要新引用但仓库里没有时，会停下来问你。

## 仓库结构

```
paper.tex              ← 你的论文（被优化的对象）
paper_diff.tex         ← 运行结束后生成：相对原稿的标注 diff
reviewer.py            ← 固定的评审引擎——不要改
check_diff.py          ← 验证 paper_diff.tex 的标注是否合法
program.md             ← agent 的完整运行协议
autopaper.toml         ← 模型配置和 API key（已 gitignore）
autopaper.example.toml ← 配置模板（已提交）
.autopaper/            ← agent 的工作记忆
results/               ← 可选：原始数据、人工笔记
```

## 局限

评审打分基于 LaTeX 源码而非编译后的 PDF——它看不到你的图表和渲染后的表格。`review_score` 是有用的优化信号，但不能替代真正的同行评审。
