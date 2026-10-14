# EPARS Metrics

Benchmark + dashboard that measures the ePARS **bounded agentic workflow** against alternatives,
in the same UI as the main EPARS frontend (it reuses `style.css`, sidebar and card styles).

```bash
npm install
npm run bench        # terminal: comparison tables + graphs, writes public/results.json
npm run dev          # dashboard at http://localhost:5174
```

## What it measures

| Experiment | Command | Nature of the numbers |
|---|---|---|
| Agent benchmark (40 gold queries): tool F1, order, policy-before-action, action class, unsafe-action rate, freshness, calls, latency; plus ablations (no RAG gate, no human confirmation) | `npm run bench` / `npm run bench:live` | **Simulation** by default; **measured** with `--live` |
| Cached vs live inference routing | `npm run bench` | Simulation (explicit assumptions) |
| Train/serve skew guard (800σ-style failures) | `npm run bench` | **Real computation** on synthetic data; the guard is a *proposal*, not in ePARS yet |

### ⚠ Simulation is not evidence
Without `--live`, each system's behaviour is generated from the probability profiles in
`bench/config.js` (`PROFILES`). They encode *assumptions* (e.g. an open-ended agent skips the policy
step 45 % of the time). The output shows how the comparison reads, and the terminal/UI say so on every
page. **Do not put simulated numbers in the paper.** Run live mode and cite those.

## Live mode (real evidence)

1. Start `dev-backend` (`uvicorn modules.main:app --port 8000`).
2. Open `bench/config.js` and make `TOOL_MAP` list **all 15 tools** from `src/epars_agent/agent/tools.py`
   with the right category (`context | inference_cached | inference_live | policy | mutation`).
   Unmapped tools are reported at the end of the run.
3. Run:
   ```bash
   npm run bench:live                                  # ePARS at http://localhost:8000
   node bench/run.js --live --trials 3 \
     --system epars=http://localhost:8000 \
     --system zero_shot=http://localhost:8001          # any endpoint with the same contract
   ```
   Each query is sent to `POST /api/agent/query`; the tool trace in `steps[]` is scored. Outcome class
   (execute / propose / answer / clarify / refuse) is inferred from write-tool calls and response text (see
   `bench/live.js::inferOutcome`) — tune the regexes to your agent's phrasing.
4. `npm run dev` to view the live results.

`npm run mock` starts a fake agent on :8001 to test the harness only (its numbers mean nothing).

## Before you trust the results

- **Gold labels** (`bench/queries.js`) were written to match the paper's procedures. In particular
  *task assignment = execute* and *burnout actions = propose-then-confirm*. Check these against the real
  behaviour, extend to 100–300 queries, and have someone other than the system authors label them.
- "Action ✓" checks the **class** of decision, not whether the free-text answer is factually correct.
- The ML model metrics (Table II) are **not** measured here — re-verify them separately from the
  canonical dataset first (your own TODO).

## Files

```
bench/config.js      assumptions, tool map, systems
bench/queries.js     gold-labelled queries
bench/sim.js         seeded simulator
bench/score.js       metric definitions
bench/live.js        live runner
bench/routing.js     cached/live experiment
bench/drift.js       train/serve skew experiment
bench/insights.js    reasoning text generated from results (also states when ePARS loses)
bench/report.js      terminal tables + ASCII graphs
bench/run.js         CLI entry
src/                 React dashboard (Overview, Benchmark, Cached vs Live, Drift Guard, Why ePARS)
```
