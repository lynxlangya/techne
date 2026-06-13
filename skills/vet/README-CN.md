# vet

`vet` 是一个「证据门控」代码 review skill。它要求 reviewer 先用 git 锚定
PR / branch 的真实 diff，再核算变更符号的影响半径、核对 claim 和 citation，
最后只能给出结构上可接受的 verdict。

适用场景：

- PR review。
- branch / commit range review。
- 合并前检查。
- 针对真实 git diff 判断「能不能 approve」。

不适用于纯设计讨论、全仓库体检，也不负责修 bug。修复是 review 之后的独立任务。

## 快速使用

先捕获 PR claim：

```bash
gh pr view 123 --json title,body --jq '.title + "\n\n" + (.body // "")' > /tmp/pr-123-claims.txt
```

锚定 review：

```bash
python3 skills/vet/scripts/vet_gate.py init \
  --project /path/to/project \
  --review pr-123 \
  --base origin/main \
  --head HEAD \
  --claims-file /tmp/pr-123-claims.txt
```

填写 `.techne/review/pr-123/review.json`，然后检查并收口：

```bash
python3 skills/vet/scripts/vet_gate.py check --project /path/to/project --review pr-123
python3 skills/vet/scripts/vet_gate.py close --project /path/to/project --review pr-123 --verdict request-changes
```

`.techne/` 是目标项目里的生成产物，不要提交到 techne 仓库。

## Verdict

- `approve`：所有 refs、hunks、claims、测试说明都已核算，且没有 blocking finding。
- `request-changes`：至少一个 `blocking` 或 `concern` finding。只有存在 R2/R3
  的 `blocking` finding 时才允许提前停止影响半径核算，`verdict.json` 会记录
  `blastRadiusComplete: false`。
- `blocked`：review 无法诚实完成，必须带 `--reason`。

完整 JSON 契约见 [reference.md](reference.md)，fixture 和经验验收见
[eval.md](eval.md)。
