# viz

`viz` 是 techne 的代码库画图 skill。它不是凭印象画架构图，而是先扫描真实仓库，选择合适的图表类型，读取证据文件，再生成 Mermaid、校验语法、写入目标项目的 `.techne/viz/`，并构建一个本地静态查看器。

适合用在这些场景：

- 接手一个 macOS、前端、后端、全栈或 monorepo 项目。
- 想快速看清模块、服务、入口、状态流转或数据关系。
- 做 code review 前，需要一张有证据的结构图。
- 排查请求链路、任务链路、状态机或类型关系。

英文版：[README.md](README.md)。

## 安装或更新

Claude Code 原生插件：

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

如果已经安装过：

```bash
claude plugin update techne
```

Codex 使用 Agent Skills：

```bash
npx skills add lynxlangya/techne --skill viz -a codex -g -y
npx skills update viz -g -y
```

其他宿主看根目录 [INSTALL.md](../../INSTALL.md)。

## 快速使用

进入目标项目后，在 Claude Code 中这样问：

```text
/techne:viz
请扫描当前仓库，画 architecture 图。先判断项目形状，列出读取过的证据文件，控制在 12-15 个顶层节点内，校验 Mermaid，写入 .techne/viz/，并构建本地 viewer。
```

在 Codex 或其他 Agent Skills 宿主中这样问：

```text
使用 viz skill。请扫描当前仓库，画 architecture 图。先判断项目形状，列出读取过的证据文件，控制在 12-15 个顶层节点内，校验 Mermaid，写入 .techne/viz/，并构建本地 viewer。
```

一次好的结果应该包含：

- 它选择的 `diagramKind`。
- 项目形状或本次限定范围。
- 画图前实际读取的证据文件。
- 通过校验的 Mermaid 源码。
- 目标项目里的 `.techne/viz/*.md`、`.index.json` 和 `index.html`。

不要把 `.techne/` 提交进项目仓库。

## 支持的图表类型

| 你想看什么 | `diagramKind` | Mermaid 类型 | 适合场景 |
| --- | --- | --- | --- |
| 项目、模块、服务、包结构 | `architecture` | `flowchart` / `graph` | 仓库结构、应用边界、服务依赖、基础设施关系。 |
| 请求、命令、任务或参与者流程 | `interaction` | `sequenceDiagram` | 登录、同步、队列任务、CLI 命令。 |
| 表、实体和持久化关系 | `data-model` | `erDiagram` | SQL migration、ORM model、schema。 |
| 状态或工作流生命周期 | `state-model` | `stateDiagram-v2` / `stateDiagram` | 订单状态、审核流程、reducer、状态机。 |
| class、interface、protocol、struct 或公开类型 | `type-structure` | `classDiagram` | 某个模块内的类型结构。 |

## 推荐测试方式

### macOS 项目

```text
/techne:viz
请扫描当前 macOS 项目，画 architecture 图。重点识别 Xcode / SwiftPM、targets、App entry、SwiftUI/AppKit 边界、本地存储、网络层、extension 或后台任务。只画从文件读到证据的关系。
```

### 前端项目

```text
/techne:viz
请扫描当前前端仓库，画 architecture 图。重点识别 package manager、workspace、应用入口、routes、state 管理、API client、构建和部署配置、主要 feature modules。控制在 12-15 个顶层节点内，超出就拆图。
```

### 请求链路

```text
/techne:viz
请画登录流程的 interaction / sequenceDiagram。从 route/page entry 到表单提交、校验、状态更新、API client、错误处理和导航。每个 participant 和 message 都要来自实际读取的文件。
```

### 数据模型

```text
/techne:viz
请画当前项目的数据模型，用 data-model / erDiagram。只根据 schema、migration、ORM/entity declaration 画实体和关系；没有外键或关联声明证据的关系不要画。
```

### 状态流转

```text
/techne:viz
请画订单状态流转，用 state-model / stateDiagram-v2。先找到状态枚举、reducer、guard、workflow 或 transition handler，再画真实转移。
```

### 类型结构

```text
/techne:viz
请针对 Settings 模块画 type-structure / classDiagram。范围只覆盖 public-facing 类型、protocol/interface、主要 view model 和 service 依赖，不要画全项目。
```

## 输出

`viz` 会把生成的图写进目标项目，而不是 techne 自己：

```text
.techne/
  viz/
    <diagram>.md
    .index.json
    index.html
```

查看器是一个自包含的静态 HTML 文件，不需要本地服务器或网络请求：

```bash
open .techne/viz/index.html
```

## 结果检查

测试时重点看：

- 是否选对图表类型。
- 节点和关系是否都有文件证据。
- 有没有编造模块、调用、状态、实体或类型关系。
- 图是否被控制在可读复杂度内。
- Mermaid 是否通过校验。
- `.techne/viz/index.html` 是否能直接打开并渲染。
- 是否避免提交 `.techne/` 生成物。

## 边界

当前版本不支持任意 Mermaid 图。Gantt、pie、journey、timeline、mindmap、Git graph、C4、quadrant、requirement、packet、Sankey 等图族暂不支持。

当它无法读取项目文件、图表类型不明确、范围没有边界、代码证据不足或 Mermaid 校验失败时，`viz` 应该停下来问你，而不是硬画。
