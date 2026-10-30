# Skills — where they came from

> **In this public copy** only the three skills written for Balıkçıl are
> included: `ledger`, `instruction` and `wall-audit`. The nine skills taken from
> the two MIT-licensed repositories below, their licence files and
> `FINGERPRINTS.txt` stay in the private repository; the sources, pinned
> commits and licences are listed here so they can be fetched from upstream.

Most of the skills in this folder are **ready-made, written by other people.**
The three written from scratch encode Balıkçıl's own rules; nothing in the
ready-made ecosystem covers those.

Every file's SHA-256 fingerprint is in `FINGERPRINTS.txt` (RULES 2). Sources
were downloaded **pinned to a commit**, so the same input gives the same result
(RULES 29). If the upstream repository changes, our copy does not — deliberately.

---

## Taken from outside

### agiprolabs/claude-trading-skills · MIT · commit `981e1d7`
`https://github.com/agiprolabs/claude-trading-skills`
Licence text: `LICENSE-agiprolabs.md` · Copyright: AGIPro

**6 of the repository's 68 skills** were taken. The whole plugin was not
installed: as a plugin it added ~4,016 tokens to every session, and 60 of its
skills (Solana MEV, crypto tax, weather markets, DEX liquidity) are not this
laboratory's domain. Worse, its `slippage-modeling` skill explains Solana AMM
mathematics; asked about costs on a Binance perpetual future, it risked
answering from the wrong domain (RULES 14).

| skill | what it is for | step |
|---|---|---|
| `walk-forward-validation` | time-series-aware splits, purging, embargo, overfit detection | 6 · 8 |
| `ohlcv-processing` | resampling, gap handling, anomaly detection, merging sources | 2 |
| `correlation-analysis` | cross-asset correlation, regime-dependent correlation | RULES 13 |
| `vectorbt` | vectorized backtesting, parameter sweeps | 8 |
| `market-microstructure-traditional` | order book dynamics, price formation, execution quality, CEX–DEX differences | 3 · 8 |
| `portfolio-analytics` | return and risk measurement, drawdown, rolling analysis | 8 |

**Careful — `walk-forward-validation` carries two hardcoded thresholds:**
"DSR below 0.95" and "PBO above 0.50". These are **not** Balıkçıl's rules.
Balıkçıl's chance line is written in RULES 12: the answers are shuffled 1,000
times and the real result must fall inside the best 1%. **In a conflict, RULES
wins.** Adding DSR/PBO to the passing condition is a rule change: the user is
asked first, then it goes into `LEDGER.md`.

### shakeebshaan/claude-code-quant-skills · MIT · commit `6b39f8f`
`https://github.com/shakeebshaan/claude-code-quant-skills`
Licence text: `LICENSE-shakeebshaan.txt` · Copyright: Shaan Shaik

| skill | what it is for | for whom |
|---|---|---|
| `strategy-critique` | an 18-question adversarial review: is the edge real, who is losing on the other side, why hasn't arbitrage eaten it, in which regime does it break | Viktor |
| `backtest-review` | audits a backtest: look-ahead bias, overfitting, unrealistic assumptions, regime dependence | Viktor · Mateo |
| `data-scrub` | data audit: missing bars, timezone drift, stale ticks, duplicate timestamps, survivorship | Mateo |

`strategy-critique` extends Viktor's five questions, it does **not** replace
them. His red stamp and the requirement to give reasoning (RULES 32) stay in his
definition.

---

## Installed as plugins (not copied, `--scope project`)

| plugin | source | contents | cost |
|---|---|---|---|
| `duckdb-skills` 0.2.4 | official marketplace · DuckDB Foundation · SHA-pinned | `read-file` `query` `attach-db` `convert-file` `s3-explore` `spatial` `duckdb-docs` `install-duckdb` `read-memories` | ~995 tok |
| `quantitative-trading` 1.2.3 | `wshobson/agents` · MIT · Seth Hobson | skills: `backtesting-frameworks` `risk-metrics-calculation` · agents: `quant-analyst` `risk-manager` | ~365 tok |

**`read-memories` is never run in Balıkçıl.** It searches past session logs, and
this machine holds session logs from the old project (RULES 1). The ban is
recorded as item 5 of the `wall-audit` skill.

**The `quant-analyst` and `risk-manager` agents are not Balıkçıl's team.** The
team is in `TEAM.md`. They arrived with the plugin; they are not used. A
coordinator who runs them has stepped outside the team.

---

## Written for Balıkçıl

No ready-made equivalent was found for these; each encodes this laboratory's own
rules.

| skill | which rule |
|---|---|
| `ledger` | appends to `LEDGER.md` only, reads the clock from the system (RULES 23, 30) |
| `instruction` | writes the instruction, runs the leak check, saves the full copy under `instructions/` (RULES 3, 4, 24) |
| `wall-audit` | audits the wall: leaks, steers, exam access, stale settings paths (RULES 1–5) |

---

## Usage limit — important

All of these skills are for **mechanical** work: writing scripts, preparing
data, measuring, auditing. Two of them (`strategy-critique`, `backtest-review`)
are for critique.

**None of them is used while writing a watcher instruction.** A watcher is told
what it may look at, never what to look for (RULES 3). If the coordinator reads
a skill and puts an idea drawn from it into a watcher instruction, the
coordinator has breached the laboratory's wall by their own hand. The skills
serve Mateo's scripts, Greta's measurement and Viktor's critique.

No agent definition carries the `Skill` tool: no agent can call a skill and walk
around this limit.
