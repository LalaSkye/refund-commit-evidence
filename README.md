# The £25 Refund Test — delayed withdrawal

**If the receiver can't establish that the approval still stands, what does the ledger actually record?**

**Zero refund effects.** The receiver returned `HOLD` and wrote neither a decision nor a refund effect to the ledger. The HOLD observation is in the run log.

## What we tested

One synthetic £25 refund (2500 pence, GBP). Two SQLite databases: one holds the approval at its source, the other holds the receiver's ledger. Both start with the same approval. We then withdrew the approval at the source, held back delivery to the receiver, and made the source unavailable. The receiver still held its old copy of the approval.

| Checkpoint | Decision | Refund effects in ledger |
| --- | --- | ---: |
| Approval withdrawn at source, delivery delayed, source unavailable | `HOLD` | **0** |
| Source reachable again, same request retried | `REFUSE` | 0 |
| **Matched control:** approval still active, source available | `COMMIT` | 1 × £25 |
| **Deliberately unsafe control:** receiver trusts its old copy after withdrawal | `COMMIT` | 1 × £25, committed after withdrawal |

The unsafe control shows that the ledger observation can reveal an effect committed after withdrawal in this schedule.

## What HOLD means here

`HOLD` is a non-final answer. The receiver writes nothing (no decision, no effect) and checks the same request afresh on retry. The zero-effect observation at HOLD is in `RUN.jsonl`. The retained database for that schedule shows the later state, after `REFUSE`.

## How the conditions were simulated

- **Delay:** the harness postpones copying the withdrawal into the receiver's inbox.
- **Source unavailable:** the harness's source callback returns no current authority.
- The standing check and the ledger write are separate steps on separate files. **No cross-database atomicity is claimed.**

## Run record

- **Captured:** 22 November 2026, 09:02:23 UTC, one local run by Trinity / Codex for AlvianTech.
- **Recorded runtime:** Python 3.12.14, SQLite 3.53.1.
- **Archive:** [delayed-withdrawal-local.zip](evidence/delayed-withdrawal-local.zip) · SHA-256 `aebee7ff4610187ce8ba8df98a19cd54bf901745292f4b13b2835ee7d521b46d`
- `SHA256SUMS` inside the archive covers every payload file.
- **Local rerun.** Independent reproduction remains open.

The archive retains its original “Private review copy” label as part of the historic record. Published here byte for byte, it retains the checksum above.

## Reproduce

[![Reproduce refund test](https://github.com/LalaSkye/refund-commit-evidence/actions/workflows/reproduce.yml/badge.svg?branch=main)](https://github.com/LalaSkye/refund-commit-evidence/actions/workflows/reproduce.yml)

With Python 3.11 or later, from a checkout run:

    python tools/reproduce.py

The workflow was written and checked locally by GitHub Copilot. GitHub's runners
run inside Ricky's own repository and custody: this is a repeat, not independent
reproduction. Independent reproduction means someone outside forks the named
commit and runs it in their own account.

## Rerun it yourself

**Prerequisite:** Python 3 with the standard-library `sqlite3` module. No other dependencies. The original capture used the runtime above.

Extract the archive and run:

    python -B checkpoint.py

The command uses temporary databases and prints one line per checkpoint. Its first line gives the SQLite version and request hash. The packaged `RUN.jsonl` also records capture time and Python version, added by the capture step, and the packaged `databases/` folder keeps the final files from that run.

## Scope

Synthetic, local and sequential. No real payments, network faults, arbitrary interleavings or cross-system commit ordering.

## Earlier experiment

An earlier single-database test checked commit order between withdrawal and refund. It ran on a GitHub-hosted runner on 22 November 2026. Its evidence is retained privately and is not part of this release.

## Related work

[Harmonic by Solace's receiver guide](https://www.solace-harmonic.com/docs/receiver-commit-controls.md) describes a SQLite reference receiver for a synthetic settlement ledger. It requires that freshness be established before commitment, and in its challenge model unresolved standing requires a hold. This test is a small, runnable case of what one receiver's ledger shows when freshness can't be established.

## Licence

The MIT licence applies only to `checkpoint.py` inside the archive. See [the licence notice](LICENSE.md).
