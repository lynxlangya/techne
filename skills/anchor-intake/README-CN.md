# anchor-intake

`anchor-intake` 是一个在开工前审问书面工程实现 brief 的 techne skill。它会强制 AI 协作者按固定的 10 项 rubric 逐项核对，把 `present` / `present-weak` 锚定到 brief 原文 span，暴露缺口、solution-as-goal 陷阱和矛盾，再输出 intent-level 的计划。

适用于 ticket、PRD、设计说明、较完整的工程实现 brief。不适用于裸的一句话需求、非工程文档、代码 review、bug 修复或直接执行。

英文版：[README.md](README.md)。

## 安装或更新

Claude Code 原生 plugin：

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

如果已经安装过 techne：

```bash
claude plugin update techne
```

Codex 常规安装建议用根目录 [INSTALL.md](../../INSTALL.md) 的整套安装：

```bash
npx skills add lynxlangya/techne -a codex -g -y
```

如果只想单独安装 `anchor-intake`：

```bash
npx skills add lynxlangya/techne --skill anchor-intake -a codex -g -y
npx skills update anchor-intake -g -y
```

其他宿主和兜底安装方式见根目录 [INSTALL.md](../../INSTALL.md)。

## 快速开始

在目标项目里打开 agent，并提供书面 brief。

Claude Code：

```text
/techne:anchor-intake
Interrogate this implementation brief before planning:
<粘贴 ticket / PRD / design note>
```

Codex 或其他 Agent Skills 宿主：

```text
Use the anchor-intake skill. Interrogate this engineering implementation brief before
planning:
<粘贴 ticket / PRD / design note>
```

一次好的 intake 应该包含：

- 将 brief 捕获到 `.techne/plan/<slug>/brief.txt`。
- 固定 rubric 的每个元素都被标记为 `present`、`present-weak` 或 `gap`。
- `present` 和 `present-weak` 都有可验证的原文 citation。
- `present` 的 `valueItems` 都由原文 span 机械 grounding。
- 每个 weak / gap 都有依赖问题。
- 如存在 solution-as-goal 或 contradiction，必须锚定到原文 span。
- 最终生成 `intakeReport.json` 和 `plan.json`。

不要提交 `.techne/` 输出。脚本会在目标项目需要时把 `.techne/` 加进 `.gitignore`。

## 脚本用法

从 brief 文件初始化：

```bash
python3 /path/to/techne/skills/anchor-intake/scripts/intake_gate.py init \
  --project /path/to/project \
  --plan login-brief \
  --brief-file /tmp/login-brief.txt
```

写好 `.techne/plan/login-brief/intake.json` 后检查：

```bash
python3 /path/to/techne/skills/anchor-intake/scripts/intake_gate.py check \
  --project /path/to/project \
  --plan login-brief
```

检查通过后 finalize：

```bash
python3 /path/to/techne/skills/anchor-intake/scripts/intake_gate.py finalize \
  --project /path/to/project \
  --plan login-brief
```

如果捕获的 artifact 不是工程实现 brief：

```bash
python3 /path/to/techne/skills/anchor-intake/scripts/intake_gate.py finalize \
  --project /path/to/project \
  --plan login-brief \
  --unscopable \
  --reason "This is a marketing brief, not an engineering implementation brief."
```

## 写入内容

`anchor-intake` 会在目标项目写入生成物：

```text
.techne/
  plan/
    <slug>/
      brief.txt
      context.json
      intake.json
      report.json
      plan.json
      intakeReport.json
```

## 边界

- v1 只支持 POSIX：macOS 和 Linux 开发环境。
- v1 只有一个 rubric：工程实现 brief。
- 门禁会验证 span 和 value grounding，但不会机械判断一个 grounded value 是否语义上回答了正确 rubric 元素。
- false gap 和问题实质仍是经验验证面，不是硬门禁。
- 输出是 intake report 和 intent-level plan，不是实现。
