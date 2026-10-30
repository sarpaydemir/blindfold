# A cheap outside judge, calibrated against a notarised key

Source: the private repository's `LEDGER.md`, entries 2026-09-19 22:55 UTC to 2026-09-20 00:00 UTC, and `external/calibration/REPORT.md` (SHA-256 `a679c11f…d088`). The scripts (`19`–`23`), the memo and the artefacts are not published: they target an undocumented provider endpoint, and the items are lines from the watchers' notes.

## The offer

A memo arrived from outside the lab: a typed-decision model, reached through OpenRouter, that returns a label, per-option probabilities and a confidence for a fraction of a cent. The suggestion was to use it to cut costs, accepting its answers above a confidence threshold. The model was absent from the provider's public model list.

`RULES.md` covered only what may come into the lab, not what may leave it, so calling an outside service was an open question. I decided it: the service may be called. The coordinator measured it before any use. Four synthetic probes, with no lab content, showed it worked (HTTP 200, 0.44 s, about $0.000014 a call).

## The design: the key exists before the first answer

The data engineer built 100 items from the watchers' round-1 notes, 25 per watcher, by a published rule and seed. Items and key went into separate files, so the script that called the endpoint could not read a label.

Before the first item call, the run posted **only the key's SHA-256** to the endpoint and kept the response. The provider's own response id carries its clock: the key was notarised at provider time 1789859632; the first item call came **66 seconds later**. The comparison script, the first one that reads a label, checks both facts and exits if either fails.

## Results: 300 calls against the key

| question | result | baseline |
|---|---|---|
| FIELD: which watcher wrote this line (4 options) | **73/100** | 25% uniform |
| CARDCOUNT: a mechanical count, key certain | **100/100** | 52% majority |
| CERTAINTY: the watcher's own 1–5 confidence digit | **37/100** exact | **51/100** for always answering "4" |

**On CERTAINTY it lost to a constant** (within ±1: 87% against 95% for the constant).

The memo's threshold idea failed on this data. Accept-above-0.9 let **4 of 27 FIELD errors** through, one at confidence 1.00 with probability 0.00 on the correct option, while escalating 47 of 100 items, 24 of them already correct. On CERTAINTY, confidence did not separate right from wrong (0.376 wrong, 0.350 right). For two-option questions the confidence was exactly top probability minus second probability in 100/100 cases: a restatement, not a second signal.

The run also found the memo wrong or silent on 12 points of the response contract: the `score` sits on a 0-based index scale, an empty input is answered at confidence 0.99 instead of refused, a truncated JSON body is parsed leniently.

The data engineer's own caution on the best number: the FIELD key is provenance, not truth. Some disagreements are a watcher writing outside its own field. *"73% is a lower bound on something and an upper bound on nothing."*

**Cost: $0.0116959 for 402 calls**, $0.0000667 per item for all three questions. Median latency 0.34 s, 300 of 300 calls HTTP 200.

## Verdict

The model got no role. Every role in `TEAM.md` was excluded on written grounds: watchers must say why they think so and the model gives no reasoning; jurors must cite file and line; the exam candidates are the measurement itself; the judge is a script. The data engineer's summary: *"it was reliable exactly where a script would have been reliable anyway."*

I approved the coordinator's recommendation: **keep the record, cut the capability.** The calibration files stayed, so nobody would repeat the experiment and believe a different number. The key's value was removed from `.env`, because a live credential beside the only role with `Bash` had no remaining use.

The earlier entry that read the four synthetic probes as "the model signals when it is guessing" was withdrawn in the ledger, not edited: at 100 real items it was wrong at confidence 1.00.
