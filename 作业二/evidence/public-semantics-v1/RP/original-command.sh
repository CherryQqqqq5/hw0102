cat <<'EOF' > /app/task_file/scripts/solution_packer.py
#!/usr/bin/env python3
"""Shape-aware LLM inference batching packer.

Strategy
--------
The cost model charges every request in a batch using the batch's ACTUAL
S_max = max aligned prompt and G_max = max gen_len, so mixing dissimilar
requests is what inflates cost/pad/latency.  The declared `shape` only drives
the (one-off) per-shape compile cost.  Therefore:

  * group requests by identical aligned seq S (so S_max == every req's S),
  * inside an S group, sort by gen_len and split into batches whose
    gen_len spread stays within a relative tolerance (controls G_max padding),
  * keep the very highest-latency requests as singletons (protects p95),
  * declare a compact per-bucket ladder of <=4 shapes drawn from real S values
    (<=8 unique shapes across both buckets) to keep compile cost low.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, '/app/task_file/scripts')
from cost_model import CostModel, align, HEADS, HIDDEN  # noqa: E402

ROOT = '/app/task_file'
GRAN = 64
MAX_SHAPES = 8
cm = CostModel(GRAN)


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def self_latency(r):
    """Latency of a request running alone in a batch (incl. batch overhead)."""
    S = align(r['prompt_len'], GRAN)
    G = r['gen_len']
    n = G
    sum_sq = cm._sum_sq_arith(S, n)
    sum_lin = n * S + n * (n - 1) / 2
    lat_d = cm.c.Td_attn * sum_sq + cm.c.Td_mlp * HIDDEN * sum_lin
    return cm._prefill_lat(r['prompt_len']) + lat_d + cm.c.Tbatch_overhead_ms


def make_ladder(S_values, k):
    """Up to k representatives chosen from real aligned S values (quantiles)."""
    u = sorted(set(S_values))
    if len(u) <= k:
        return u
    idx = [int(round(i * (len(u) - 1) / (k - 1))) for i in range(k)]
    return sorted({u[i] for i in idx})


def build(reqs, ladder, tol, maxb, lat_cut):
    byS = defaultdict(list)
    for r in reqs:
        byS[align(r['prompt_len'], GRAN)].append(r)

    batches = []
    singles = 0
    for S, rs in sorted(byS.items()):
        hi = [r for r in rs if self_latency(r) > lat_cut] if lat_cut > 0 else []
        if hi:
            singles += len(hi)
            for r in hi:
                batches.append([r])
            rs = [r for r in rs if self_latency(r) <= lat_cut]
        if not rs:
            continue
        rs.sort(key=lambda r: r['gen_len'])
        cur = [rs[0]]
        gmin = rs[0]['gen_len']
        for r in rs[1:]:
            g = r['gen_len']
            if len(cur) >= maxb or (g - gmin) > tol * max(1, gmin):
                batches.append(cur)
                cur = [r]
                gmin = g
            else:
                cur.append(r)
        batches.append(cur)

    batches.sort(key=lambda b: (align(b[0]['prompt_len'], GRAN),
                                min(x['gen_len'] for x in b),
                                len(b)))
    recs = []
    used = set()
    for i, b in enumerate(batches):
        need = max(align(r['prompt_len'], GRAN) for r in b)
        shp = next(x for x in ladder if x >= need)
        used.add(shp)
        bid = 'b-%04d' % (i + 1)
        for r in b:
            recs.append({
                'request_id': r['request_id'],
                'batch_id': bid,
                'shape': {'seq_align': shp, 'heads_align': HEADS,
                          'hidden_align': HIDDEN},
            })
    return recs, used, singles


def validate(reqs, recs, shapes_global):
    by_id = {r['request_id']: r for r in reqs}
    got = [x['request_id'] for x in recs]
    assert len(got) == len(set(got)), 'duplicate request_id in plan'
    assert set(got) == set(by_id), 'missing/extra request_ids'
    per_batch = defaultdict(set)
    for x in recs:
        sh = x['shape']
        assert sh['heads_align'] == HEADS, 'bad heads_align'
        assert sh['hidden_align'] == HIDDEN, 'bad hidden_align'
        assert sh['seq_align'] % GRAN == 0, 'seq_align not multiple of 64'
        assert sh['seq_align'] >= align(by_id[x['request_id']]['prompt_len'], GRAN), \
            'seq_align too small for %s' % x['request_id']
        per_batch[x['batch_id']].add(
            (sh['seq_align'], sh['heads_align'], sh['hidden_align']))
    for bid, s in per_batch.items():
        assert len(s) == 1, 'mixed shapes in batch %s' % bid
    assert len(shapes_global) <= MAX_SHAPES, 'too many shapes: %d' % len(shapes_global)
    return True


TH = {
    'b1': {'cost': 3.0e11, 'pad': 0.055, 'p95': 2.1e6, 'seq': 2.7e8},
    'b2': {'cost': 4.8e10, 'pad': 0.15, 'p95': 2.1e5, 'seq': 3.2e7},
}


def ratios(m, t):
    r = {
        'cost': m['cost'] / t['cost'],
        'pad': m['pad_ratio'] / t['pad'],
        'p95': m['p95_latency_ms'] / t['p95'],
        'seq': m['sequential_timecost'] / t['seq'],
    }
    r['worst'] = max(r.values())
    return r


def sweep(reqs, key, k_ladder):
    ladder = make_ladder([align(r['prompt_len'], GRAN) for r in reqs], k_ladder)
    lats = sorted(self_latency(r) for r in reqs)
    p97 = lats[int(0.97 * (len(lats) - 1))]
    p93 = lats[int(0.93 * (len(lats) - 1))]
    cuts = [0] + [p97, p93]
    best = None
    for lat_cut in cuts:
        for tol in (0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.25):
            for maxb in (2, 4, 8, 16, 32):
                recs, used, singles = build(reqs, ladder, tol, maxb, lat_cut)
                pm = {r['request_id']: r for r in reqs}
                m = cm.plan_metrics(pm, recs)
                rt = ratios(m, TH[key])
                if rt['worst'] < 1.0 and (best is None or rt['worst'] < best[0]):
                    best = (rt['worst'], lat_cut, tol, maxb, recs, used, m, rt, singles)
    return best, ladder


def dump(name, best, ladder, key):
    worst, lat_cut, tol, maxb, recs, used, m, rt, singles = best
    nb = len(set(x['batch_id'] for x in recs))
    print('%s: tol=%.2f maxb=%d lat_cut=%.3e singles=%d batches=%d used_shapes=%s'
          % (name, tol, maxb, lat_cut, singles, nb, sorted(used)))
    print('   cost=%.4e (%.1f%% of thr)  pad=%.4f (%.1f%%)  p95=%.4e (%.1f%%)  seq=%.4e (%.1f%%)  worst=%.3f'
          % (m['cost'], 100 * rt['cost'], m['pad_ratio'], 100 * rt['pad'],
             m['p95_latency_ms'], 100 * rt['p95'], m['sequential_timecost'],
             100 * rt['seq'], worst))


def main():
    b1 = load(ROOT + '/input_data/requests_bucket_1.jsonl')
    b2 = load(ROOT + '/input_data/requests_bucket_2.jsonl')

    best1, lad1 = sweep(b1, 'b1', 4)
    best2, lad2 = sweep(b2, 'b2', 4)
    assert best1 is not None, 'no feasible plan for bucket 1'
    assert best2 is not None, 'no feasible plan for bucket 2'
    dump('bucket1', best1, lad1, 'b1')
    dump('bucket2', best2, lad2, 'b2')

    recs1, recs2 = best1[4], best2[4]
    global_shapes = best1[5] | best2[5]
    validate(b1, recs1, global_shapes)
    validate(b2, recs2, global_shapes)
    print('global unique shapes: %s (count=%d)' % (sorted(global_shapes), len(global_shapes)))

    os.makedirs(ROOT + '/output_data', exist_ok=True)
    for path, recs in ((ROOT + '/output_data/plan_b1.jsonl', recs1),
                       (ROOT + '/output_data/plan_b2.jsonl', recs2)):
        with open(path, 'w') as f:
            for x in recs:
                f.write(json.dumps(x) + '\n')
        print('wrote %s (%d records)' % (path, len(recs)))
    print('ALL THRESHOLDS MET WITH MARGIN')


if __name__ == '__main__':
    main()
EOF
cd /app/task_file/scripts && python3 solution_packer.py
