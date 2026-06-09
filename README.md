# techne

> **τέχνη** · /ˈtɛk.niː/ · "TEK-nee"

Ancient Greek for **craft · skill · art** — the practical know-how of *making* and *doing*, and the shared root of both **technique** and **technology**. Aristotle placed *technē* (knowing **how**) beside *epistēmē* (knowing **that**).

Skills and agents for the AI era.

<sub>技艺。古希腊语 τέχνη，是 “technique / technology” 的共同词根，指「知道怎么做」的实践之知。读作「忒克涅 / TEK-nee」。</sub>

## What This Is

techne is a curated library of skills and agent assets for practical AI-era
work. A techne skill is not a prompt snippet. It is a forced cognitive move: a
small procedure that makes an AI collaborator investigate, judge, write, code,
or ship in a way it often skips under pressure.

The project keeps one shared source of truth in `skills/`. Host-specific files
stay thin: Claude Code plugin metadata, Cursor and Gemini manifests, and install
instructions for Codex, Kimi, and other Agent Skills hosts all point back to the
same skill bodies.

## Skills

- `viz` — investigate a real codebase by diagramming it. It routes one user
  request across architecture, interaction, data-model, state-model, and
  type-structure diagrams, then validates and builds a local viewer. See
  [skills/viz/README.md](skills/viz/README.md) for detailed usage.

<sub>当前种子 skill：`viz`，通过真实代码证据画架构、时序、数据模型、状态机和类型结构图，并生成本地查看器。</sub>

## Install

**Recommended — ask your AI agent.** Paste this into Claude Code or Codex:

```
Install techne for my current agent by following https://github.com/lynxlangya/techne/blob/main/INSTALL.md, then verify the viz skill is available.
```

The agent reads [INSTALL.md](INSTALL.md), detects your harness (Claude / Codex / Cursor / Gemini / Kimi), runs the right install path, and confirms the skill works.

**Manual** — per-harness commands and the universal `npx skills` fallback are in [INSTALL.md](INSTALL.md).

For Claude Code:

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

For Codex:

```bash
npx skills add lynxlangya/techne --skill viz -a codex -g -y
```

See [WORKFLOW.md](WORKFLOW.md) for the delivery process and
[ROADMAP.md](ROADMAP.md) for the product map.

<sub>安装：推荐把上面的提示词丢给 Claude / Codex，让它读 [INSTALL.md](INSTALL.md) 自行安装并验证；手动命令与 `npx skills` 兜底也在 INSTALL.md。</sub>

## Documentation

Public-facing documentation in this repository is English-first, with a Chinese
companion section for the same user-facing content. English remains the default
because host agents and external contributors parse it more reliably; Chinese is
kept close by so the maintainer and Chinese users can read the same intent
without translation guesswork.

## 中文说明

techne 是一个面向 AI 时代协作方式的 skills / agents 资源库。这里的 skill 不是一段提示词，而是一套强制执行的认知流程：让 AI 协作者在调查、判断、写作、编码或交付时，补上它在压力下经常跳过的关键动作。

项目的核心规则是：**一份 skill 正文，多套薄皮分发**。真正的 skill 内容都放在 `skills/`；Claude Code plugin、Cursor / Gemini manifest、Codex / Kimi / Agent Skills 安装路径，都应该指向同一份正文，而不是复制出多份不同版本。

### 当前 skill

- `viz`：通过画图调查真实代码库。它会根据用户问题选择 architecture、interaction、data-model、state-model 或 type-structure 图，读取真实文件证据，生成 Mermaid，校验后写入目标项目，并构建本地查看器。

详细使用方式见 [skills/viz/README.md](skills/viz/README.md)。

### 安装

推荐直接让你的 AI agent 自己安装。把这段话丢给 Claude Code 或 Codex：

```text
Install techne for my current agent by following https://github.com/lynxlangya/techne/blob/main/INSTALL.md, then verify the viz skill is available.
```

Claude Code 手动安装：

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

Codex 手动安装：

```bash
npx skills add lynxlangya/techne --skill viz -a codex -g -y
```

其他宿主和兜底命令见 [INSTALL.md](INSTALL.md)。

### 开发流程

新 skill 或带设计含量的改动遵循 [WORKFLOW.md](WORKFLOW.md)：先讨论并写 issue spec，再由 codex 红队规格，规格通过后执行，Claude 复审和经验验证，最后由维护者决定是否合并。

路线图见 [ROADMAP.md](ROADMAP.md)。
