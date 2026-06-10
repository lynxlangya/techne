# repro

`repro` 是 techne 的 bug 修复 skill。它强制 AI 协作者在改代码前先记录一次失败复现，再用同一个 probe identity 验证修复结果。

适用场景：失败测试、报错栈、崩溃、卡死、回归、错误输出、错误渲染，或者任何能写成「运行 X 现在产生 Y，但应该产生 Z」的行为问题。

English version: [README.md](README.md).

## 安装或更新

Claude Code 原生插件：

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

如果已经安装过 techne：

```bash
claude plugin update techne
```

Codex 通过 Agent Skills：

```bash
npx skills add lynxlangya/techne --skill repro -a codex -g -y
npx skills update repro -g -y
```

其他宿主和兜底命令见根目录 [INSTALL.md](../../INSTALL.md)。

## 快速开始

在目标项目里打开 agent，然后明确要求使用 `repro`。

Claude Code：

```text
/techne:repro
修复这个 bug：在 packages/app 运行 npm test 会失败，并出现 "TypeError:
cannot read properties of undefined"。先复现，再用同一个 probe 验证修复。
```

Codex 或其他 Agent Skills 宿主：

```text
使用 repro skill。修复这个 bug：login test 失败并出现 "TypeError:
cannot read properties of undefined"。先复现，再用同一个 probe 验证修复。
```

一次合格运行应该包含：

- 选择的 probe 和稳定的 `--expect` 锚点。
- 生产代码改动前的失败 ledger entry。
- 围绕失败 probe 做诊断。
- 修复后用同一个 identity 跑出通过结果。
- `close` JSON 证明已验证，或者清楚标记为 speculative。
- 强度档位：S1、S2、S3 或 S4。

不要提交 `.techne/` 输出。ledger 会按需把 `.techne/` 加到目标项目的 `.gitignore`。

## 脚本用法

运行 package-local 失败 probe：

```bash
python3 /path/to/techne/skills/repro/scripts/repro_ledger.py run \
  --project /path/to/project \
  --bug login-crash \
  --cwd packages/app \
  --expect "TypeError: cannot read" \
  --timeout 60 \
  -- npm test -- login.test.ts
```

修复后，重新运行完全相同的 probe 并 close：

```bash
python3 /path/to/techne/skills/repro/scripts/repro_ledger.py run \
  --project /path/to/project \
  --bug login-crash \
  --cwd packages/app \
  --expect "TypeError: cannot read" \
  --timeout 60 \
  -- npm test -- login.test.ts

python3 /path/to/techne/skills/repro/scripts/repro_ledger.py close \
  --project /path/to/project \
  --bug login-crash
```

如果 probe 依赖环境变量，用 shell 模式把环境变量写进命令本身：

```bash
python3 /path/to/techne/skills/repro/scripts/repro_ledger.py run \
  --project /path/to/project \
  --bug locale-sort \
  --shell \
  --expect "sort order is wrong" \
  -- LC_ALL=C npm test
```

如果确实无法复现：

```bash
python3 /path/to/techne/skills/repro/scripts/repro_ledger.py mark-unreproduced \
  --project /path/to/project \
  --bug customer-only-crash \
  --no-probe-possible \
  --reason "Requires customer-only credentials and data unavailable locally"
```

## 写入内容

`repro` 会把 ledger 写到目标项目里：

```text
.techne/
  repro/
    <bug-slug>.jsonl
```

每次运行会记录：

- probe identity：mode、argv 或 shell string、cwd、timeout。
- exit code、是否 timeout、耗时、输出 tail。
- 可选 `--expect` 匹配结果和上下文。
- 如果目标项目是 git worktree，会记录 git evidence。

## 边界

- v1 仅支持 POSIX：macOS 和 Linux 开发环境。
- Windows 是明确记录的未来目标。
- 这个 gate 防的是疏忽跳过复现，不防恶意伪造。
- `--no-stable-expect` 只用于没有稳定文本输出的症状。
- probe 改了就是新的 fail -> pass cycle，不能拿来验证旧 probe。
