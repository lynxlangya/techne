# anchor-diligence

`anchor-diligence` 用来为单个上市公司生成带引用的深度研究 dossier。它对应
finance shelf 的 vertical-analysis 工作：固定 12 项 rubric、带日期的证据快照，
以及一个会拒绝“claim 强于 citation”的机械门。

它不输出 buy/sell/hold、目标价、下单草稿或交易信号。

## 什么时候用

适合：

- “深度研究 Apple 这家公司。”
- “为 0700.HK 做一份带引用的 diligence dossier。”
- “全面梳理 NVIDIA 的商业模式、财务、竞争格局和风险。”

不适合：

- 快速查股价或 quote；
- 下单、交易或投资 verdict；
- ETF、债券、crypto、纯宏观题、非上市公司；
- 多家公司横向比较。

## 工作流

1. 用 E2 URL 解析身份：

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py init \
  --project /tmp/company-research \
  --ticker AAPL \
  --exchange NASDAQ \
  --legal-name "Apple Inc." \
  --identifier 0000320193 \
  --issuer-host investor.apple.com \
  --identity-url "https://www.sec.gov/Archives/edgar/data/320193/..."
```

2. 保存证据快照：

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py snapshot \
  --project /tmp/company-research \
  --ticker AAPL \
  --source-id annual-report \
  --source-class regulatory-filing \
  --url "https://www.sec.gov/Archives/edgar/data/320193/..."
```

没有可直接 fetch URL 的 host-relayed 证据，只能走 E1：

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py snapshot \
  --project /tmp/company-research \
  --ticker AAPL \
  --source-id analyst-consensus \
  --source-class analyst-research \
  --content-file /tmp/analyst-consensus.txt \
  --source-locator "broker-mcp://consensus/AAPL" \
  --retrieval-method broker-mcp
```

3. 编写 `.techne/anchor-diligence/<TICKER>/research.json`。

4. 检查：

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py check \
  --project /tmp/company-research \
  --ticker AAPL
```

5. 生成报告：

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py finalize \
  --project /tmp/company-research \
  --ticker AAPL
```

## 证据强度

E2 是 gate 自己通过 URL 抓取的证据；只有通过 URL、source-class、反射、日期和
grounding 检查后，才能支撑 `present`。

E1 是宿主工具转述/粘贴的证据。它可以出现在报告里，但永远只能把 claim、
subfacet 或 element 支撑到 `present-weak`。

## 输出

gate 会写入：

```text
.techne/anchor-diligence/<TICKER>/
  scope.json
  sources/
  research.json
  report.json
  reportMeta.json
  report.md
```

`report.md` 包含 Cover、Executive Summary、Deep Dive 和 Appendix。`reportMeta.json`
记录 warning 和 sourcing-strength disclosure。

## 验证状态

机械验证见 `eval.md`。经验验收是历史 backtest，按 `WORKFLOW.md` 在实现后另行执行。
