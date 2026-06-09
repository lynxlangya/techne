# techne

> **τέχνη** · /ˈtɛk.niː/ · "TEK-nee"

技艺。古希腊语 `τέχνη`，是 `technique` / `technology` 的共同词根，指「知道怎么做」的实践之知。读作「忒克涅 / TEK-nee」。

英文版：[README.md](README.md)。

## 这是什么

techne 是一个面向 AI 时代协作方式的 skills / agents 资源库。这里的 skill 不是一段提示词，而是一套强制执行的认知流程：让 AI 协作者在调查、判断、写作、编码或交付时，补上它在压力下经常跳过的关键动作。

项目的核心规则是：**一份 skill 正文，多套薄皮分发**。真正的 skill 内容都放在 `skills/`；Claude Code plugin、Cursor / Gemini manifest、Codex / Kimi / Agent Skills 安装路径，都应该指向同一份正文，而不是复制出多份不同版本。

## 当前 skill

- `viz`：通过画图调查真实代码库。它会根据用户问题选择 architecture、interaction、data-model、state-model 或 type-structure 图，读取真实文件证据，生成 Mermaid，校验后写入目标项目，并构建本地查看器。详细使用方式见 [skills/viz/README-CN.md](skills/viz/README-CN.md)。

## 安装

**推荐：让你的 AI agent 自己安装。** 把这段话丢给 Claude Code 或 Codex：

```text
Install techne for my current agent by following https://github.com/lynxlangya/techne/blob/main/INSTALL.md, then verify the viz skill is available.
```

agent 会读取 [INSTALL.md](INSTALL.md)，识别当前宿主是 Claude / Codex / Cursor / Gemini / Kimi，选择正确安装路径，并确认 skill 可用。

**手动安装：** 各宿主命令和通用 `npx skills` 兜底都在 [INSTALL.md](INSTALL.md)。

Claude Code：

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

Codex：

```bash
npx skills add lynxlangya/techne --skill viz -a codex -g -y
```

## 文档约定

公开说明文档按语言拆成两个文件：

- `README.md` 是默认英文文档。
- `README-CN.md` 是中文说明文档。

skill 的使用说明也遵循同样约定，例如 `skills/viz/README.md` 和 `skills/viz/README-CN.md`。

## 开发流程

新 skill 或带设计含量的改动遵循 [WORKFLOW.md](WORKFLOW.md)：先讨论并写 issue spec，再由 codex 红队规格，规格通过后执行，Claude 复审和经验验证，最后由维护者决定是否合并。

路线图见 [ROADMAP.md](ROADMAP.md)。
