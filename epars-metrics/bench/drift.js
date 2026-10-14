// Train/serve skew experiment — a REAL computation (no assumptions about the agent).
// We fit per-feature training statistics, then feed corrupted serving batches to
//   (a) an unguarded linear scorer  (what an LLM agent would "see"), and
//   (b) a simple pre-agent guard: row z-score threshold + batch mean-shift test.
// The guard is a *proposed* addition — it is not in the current ePARS code.
import { DRIFT as D } from "./config.js";
import { rng } from "./sim.js";

const FEATURES = [
  "technical_competence", "domain_knowledge", "overtime_ratio", "peer_productivity_gap",
  "fb_composite_rating", "output_quality", "collaboration", "task_completion_rate",
];
const W = [4, 3, -5, 2, 4, 3, 2, 3]; // fixed weights of a toy linear scorer (points per σ)

function gauss(r) { return Math.sqrt(-2 * Math.log(1 - r())) * Math.cos(2 * Math.PI * r()); }

export function runDrift(seed = 42) {
  const r = rng(seed + 7);
  const mu = FEATURES.map((_, i) => 5 + i * 0.7), sd = FEATURES.map((_, i) => 1 + i * 0.15);
  const train = Array.from({ length: D.trainRows }, () => FEATURES.map((_, j) => mu[j] + sd[j] * gauss(r)));
  const tm = FEATURES.map((_, j) => train.reduce((a, x) => a + x[j], 0) / D.trainRows);
  const ts = FEATURES.map((_, j) => Math.sqrt(train.reduce((a, x) => a + (x[j] - tm[j]) ** 2, 0) / D.trainRows));
  const clean = () => FEATURES.map((_, j) => mu[j] + sd[j] * gauss(r));

  const scenarios = [
    ["Clean serving data", "same pipeline as training", (x) => x],
    ["Subtle drift (+1σ)", "one feature shifted by 1 standard deviation", (x) => { x[2] += ts[2]; return x; }],
    ["Wrong scaling (×100)", "feature served in different units", (x) => { x[0] *= 100; return x; }],
    ["Wrong dataset generation", "feature from another dataset version (+800σ)", (x) => { x[3] = tm[3] + 800 * ts[3]; return x; }],
    ["Silently missing feature", "null imputed as 0", (x) => { x[4] = 0; return x; }],
    ["Single extreme row", "one corrupted row in the batch", (x, i) => { if (i === 0) x[1] = tm[1] + 50 * ts[1]; return x; }],
  ];

  return scenarios.map(([name, desc, mut]) => {
    const rows = Array.from({ length: D.serveRows }, (_, i) => mut(clean(), i));
    const z = rows.map((x) => x.map((v, j) => (v - tm[j]) / ts[j]));
    const preds = z.map((zr) => 50 + zr.reduce((a, v, j) => a + W[j] * v, 0));
    const maxZ = Math.max(...z.flat().map(Math.abs));
    const rowFlags = z.filter((zr) => zr.some((v) => Math.abs(v) > D.rowThresholdSigma)).length;
    const batchShift = Math.max(...FEATURES.map((_, j) => Math.abs(z.reduce((a, zr) => a + zr[j], 0) / D.serveRows)));
    const batchFlag = batchShift > D.batchK / Math.sqrt(D.serveRows);
    const outOfRange = preds.filter((p) => p < 0 || p > 100).length / preds.length;
    return {
      name, desc, maxAbsZ: maxZ, rowFlagRate: rowFlags / D.serveRows,
      batchMeanShift: batchShift, guardDetected: rowFlags > 0 || batchFlag,
      outOfRangeRate: outOfRange, meanPrediction: preds.reduce((a, b) => a + b, 0) / preds.length,
      shouldDetect: name !== "Clean serving data",
    };
  });
}
