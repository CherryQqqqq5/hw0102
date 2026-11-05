cat > /app/work/solve.py <<'EOF'
#!/usr/bin/env python3
"""Shape-aware LLM inference batching scheduler.

Stage A: exact DP over contiguous partitions of aligned prompt lengths
         -> chooses <=8 shapes (seq_align) minimising decode cost + compile cost.
Stage B: exact DP over contiguous partitions of sorted gen_len values per shape,
         with a Lagrangian multiplier lam on sequential execution time, plus an
         exact per-batch overhead term.  Sweeping lam traces the cost<->seq frontier.
Selection: pick config maximising the worst-case relative slack over the
           four thresholds (cost, pad_ratio, p95 latency, sequential timecost).
"""
import json, sys, bisect
sys.path.insert(0, '/app/task_file/scripts')
from cost_model import CostModel, align, HEADS, HIDDEN
from collections import defaultdict

G_ = 64
MAX_SHAPES = 8
CM = CostModel(G_)
C = CM.c
A_D = C.Kd_attn;  B_D = C.Kd_mlp * HIDDEN
A_L = C.Td_attn;  B_L = C.Td_mlp * HIDDEN
INF = float('inf')

IN_FMT = '/app/task_file/input_data/requests_bucket_%d.jsonl'
OUT_FMT = '/app/task_file/output_data/plan_b%d.jsonl'
TH = {1: dict(cost=3.0e11, pad=0.055, p95=2.1e6, seq=2.7e8),
      2: dict(cost=4.8e10, pad=0.15,  p95=2.1e5, seq=3.2e7)}

def load(b):
    with open(IN_FMT % b) as f:
        return [json.loads(l) for l in f if l.strip()]

def pcost(p):
    S = align(p, G_); return C.Kp_attn*S*S + C.Kp_mlp*S*HIDDEN
def plat(p):
    S = align(p, G_); return C.Tp_attn*S*S + C.Tp_mlp*S*HIDDEN
def cc(S):
    return C.Kshape_attn*S*S + C.Kshape_mlp*S*HIDDEN
def dcost_n(S, G):
    """decode cost for ONE request inside a batch with ctx S and G_max=G"""
    return (A_D*(G*S*S + S*G*(G-1) + G*(G-1)*(2*G-1)/6.0)
            + B_D*(G*S + G*(G-1)/2.0))
def dlat(S, G):
    return (A_L*(G*S*S + S*G*(G-1) + G*(G-1)*(2*G-1)/6.0)
            + B_L*(G*S + G*(G-1)/2.0))

# ---------------------------- Stage A: shape set ----------------------------
def stage_a(reqs, K=MAX_SHAPES, compile_on=True):
    uniq = sorted(set(align(r['prompt_len'], G_) for r in reqs))
    bya = defaultdict(list)
    for r in reqs:
        bya[align(r['prompt_len'], G_)].append(r)
    m = len(uniq)
    P1 = [0.0]*(m+1); P2 = [0.0]*(m+1); P3 = [0.0]*(m+1)
    for i, a in enumerate(uniq):
        c = q = t = 0.0
        for r in bya[a]:
            g = r['gen_len']; c += g; q += g*(g-1); t += g*(g-1)*(2*g-1)/6.0
        P1[i+1] = P1[i]+c; P2[i+1] = P2[i]+q; P3[i+1] = P3[i]+t
    def seg(i, j):                      # uniques i..j, shape = uniq[j]
        S = uniq[j]
        c1 = P1[j+1]-P1[i]; c2 = P2[j+1]-P2[i]; c3 = P3[j+1]-P3[i]
        v = A_D*(S*S*c1 + S*c2 + c3) + B_D*(S*c1 + c2/2.0)
        return v + (cc(S) if compile_on else 0.0)
    K = min(K, m)
    dp = [[INF]*(K+1) for _ in range(m+1)]
    pv = [[-1]*(K+1) for _ in range(m+1)]
    dp[0][0] = 0.0
    for k in range(1, K+1):
        for j in range(1, m+1):
            best, bi = INF, -1
            for i in range(k-1, j):
                if dp[i][k-1] == INF: continue
                v = dp[i][k-1] + seg(i, j-1)
                if v < best: best, bi = v, i
            dp[j][k] = best; pv[j][k] = bi
    j = m; kk = min(range(1, K+1), key=lambda x: dp[m][x])
    shapes = []
    while kk > 0:
        i = pv[j][kk]; shapes.append(uniq[j-1]); j = i; kk -= 1
    return sorted(set(shapes))

def kmeans_shapes(reqs, K=MAX_SHAPES, iters=200):
    xs = sorted(align(r['prompt_len'], G_) for r in reqs); m = len(xs)
    cs = sorted(set(xs[min(m-1, int((i+0.5)*m/K))] for i in range(K)))
    for _ in range(iters):
        k = len(cs); buckets = [[] for _ in range(k)]
        for x in xs:
            buckets[min(range(k), key=lambda t: abs(x-cs[t]))].append(x)
        new = sorted(set(max(b) for b in buckets if b))
        if new == cs: break
        cs = new
    return cs[:MAX_SHAPES]

def quant_shapes(reqs, K=MAX_SHAPES):
    xs = sorted(align(r['prompt_len'], G_) for r in reqs); m = len(xs)
    return sorted(set(xs[min(m-1, int((i+1)*m/K)-1)] for i in range(K)))

# ------------------------ Stage B: gen-bin DP (exact) ------------------------
def assign(reqs, shapes):
    out = defaultdict(lambda: defaultdict(list))
    for r in reqs:
        a = align(r['prompt_len'], G_)
        S = shapes[min(bisect.bisect_left(shapes, a), len(shapes)-1)]
        out[S][r['gen_len']].append(r)
    return out

def bin_dp(groups, S, lam):
    keys = sorted(groups)
    k = len(keys)
    cnt = [len(groups[g]) for g in keys]
    plm = [max(plat(r['prompt_len']) for r in groups[g]) for g in keys]
    dp = [INF]*(k+1); dp[0] = 0.0; pv = [-1]*(k+1)
    for j in range(1, k+1):
        G = keys[j-1]
        base = dcost_n(S, G) + C.Kbatch_overhead_cost
        dl = dlat(S, G) + C.Tbatch_overhead_ms
        best, bi, n, mp = INF, -1, 0, 0.0
        for i in range(j, 0, -1):
            n += cnt[i-1]
            if plm[i-1] > mp: mp = plm[i-1]
            v = dp[i-1] + n*base + lam*(mp + dl)
            if v < best: best, bi = v, i
        dp[j] = best; pv[j] = bi
    segs = []; j = k
    while j > 0:
        i = pv[j]; segs.append((i-1, j-1)); j = i-1
    return segs[::-1]

def build_records(reqs, shapes, lam):
    byS = assign(reqs, shapes)
    recs = []; bid = 0
    for S in sorted(byS):
        groups = byS[S]
        keys = sorted(groups)
        for (i, j) in bin_dp(groups, S, lam):
            bid += 1; b = 'b-%04d' % bid
            for t in range(i, j+1):
                for r in groups[keys[t]]:
                    recs.append({'request_id': r['request_id'], 'batch_id': b,
                                 'shape': {'seq_align': S, 'heads_align': HEADS,
                                           'hidden_align': HIDDEN}})
    return recs

def exact(reqs, recs):
    return CM.plan_metrics({r['request_id']: r for r in reqs}, recs)

def validate(reqs, recs):
    errs = []
    ids = [p['request_id'] for p in recs]
    if len(ids) != len(set(ids)): errs.append('duplicate request_id')
    if set(ids) != set(r['request_id'] for r in reqs): errs.append('missing/extra ids')
    rm = {r['request_id']: r for r in reqs}; bs = {}
    for p in recs:
        sh = p['shape']; b = p['batch_id']
        if b in bs and bs[b] != sh: errs.append('mixed shapes in batch %s' % b)
        bs[b] = sh
        a = align(rm[p['request_id']]['prompt_len'], G_)
        if sh['seq_align'] < a or sh['seq_align'] % G_: errs.append('bad seq_align %s' % p['request_id'])
        if sh['heads_align'] != HEADS or sh['hidden_align'] != HIDDEN: errs.append('bad heads/hidden')
    us = {(s['seq_align'], s['heads_align'], s['hidden_align']) for s in bs.values()}
    if len(us) > MAX_SHAPES: errs.append('too many shapes: %d' % len(us))
    return errs, us

LAMS = [0.0] + [10.0**(e/4.0) for e in range(0, 13)]   # 1 -> 1000

def candidates(reqs):
    out = {}
    for K in (8, 7, 6):
        out['dp%d' % K] = stage_a(reqs, K)
        out['km%d' % K] = kmeans_shapes(reqs, K)
        out['q%d'  % K] = quant_shapes(reqs, K)
    return out

def main():
    chosen = {}
    for b in (1, 2):
        reqs = load(b); t = TH[b]
        best = None; seen = {}
        for name, sh in candidates(reqs).items():
            if not sh: continue
            key = tuple(sh)
            if key in seen: continue
            row = None
            for lam in LAMS:
                recs = build_records(reqs, sh, lam)
                errs, us = validate(reqs, recs)
                if errs: continue
                m = exact(reqs, recs)
                r = dict(cost=m['cost']/t['cost'], pad=m['pad_ratio']/t['pad'],
                         p95=m['p95_latency_ms']/t['p95'], seq=m['sequential_timecost']/t['seq'])
                if max(r.values()) > 1.0: continue
                slack = min(1.0-x for x in r.values())
                if row is None or slack > row[0]:
                    row = (slack, lam, m, recs, us, r, name, sh)
            if row is not None:
                seen[key] = row
                if best is None or (row[0], -row[2]['cost']) > (best[0], -best[2]['cost']):
                    best = row
            else:
                seen[key] = None
        for k, v in seen.items():
            if v is None: print('   b%d infeasible shapes=%s' % (b, list(k)))
            else: print('   b%d %-4s S=%-52s lam=%-7.4g cost=%.4e pad=%.4f p95=%.3e seq=%.3e slack=%.4f'
                        % (b, v[6], v[7], v[1], v[2]['cost'], v[2]['pad_ratio'],
                           v[2]['p95_latency_ms'], v[2]['sequential_timecost'], v[0]))
        slack, lam, m, recs, us, r, name, sh = best
        chosen[b] = (recs, us)
        print('  -> bucket %d SELECTED %s lam=%g shapes=%s' % (b, name, lam, sh))
        print('     cost=%.4e (%.3fx) pad=%.4f (%.3fx) p95=%.3e (%.3fx) seq=%.3e (%.3fx)'
              % (m['cost'], r['cost'], m['pad_ratio'], r['pad'], m['p95_latency_ms'],
                 r['p95'], m['sequential_timecost'], r['seq']))

    import os
    os.makedirs('/app/task_file/output_data', exist_ok=True)
    for b in (1, 2):
        recs = chosen[b][0]
        order = {r['request_id']: i for i, r in enumerate(load(b))}
        recs = sorted(recs, key=lambda p: order[p['request_id']])
        with open(OUT_FMT % b, 'w') as f:
            for p in recs:
                f.write(json.dumps(p) + '\n')
    return chosen

chosen = main()

# ------------- independent re-validation straight from the files -------------
print('\n=== independent file check ===')
allsets = []
for b in (1, 2):
    reqs = load(b); t = TH[b]
    recs = [json.loads(l) for l in open(OUT_FMT % b)]
    m = CostModel(64)
    errs, us = validate(reqs, recs)
    met = m.plan_metrics({r['request_id']: r for r in reqs}, recs)
    allsets.append(us)
    ok = (not errs and met['cost'] <= t['cost'] and met['pad_ratio'] <= t['pad']
          and met['p95_latency_ms'] <= t['p95'] and met['sequential_timecost'] <= t['seq'])
    print('plan_b%d: n=%d batches=%d shapes=%d %s' % (
        b, len(recs), len(set(p['batch_id'] for p in recs)), len(us),
        'PASS' if ok else 'FAIL ' + ';'.join(errs)))
    print('   cost %.4e/%.2e  pad %.5f/%.3f  p95 %.4e/%.1e  seq %.4e/%.2e' % (
        met['cost'], t['cost'], met['pad_ratio'], t['pad'],
        met['p95_latency_ms'], t['p95'], met['sequential_timecost'], t['seq']))
print('union of shapes across both plans:', len(allsets[0] | allsets[1]))
EOF
cd /app/work && time python3 solve.py 2>&1 | tail -45
