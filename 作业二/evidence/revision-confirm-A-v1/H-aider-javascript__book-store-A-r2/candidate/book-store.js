const GROUP_PRICE = { 1: 800, 2: 1520, 3: 2160, 4: 2560, 5: 3000 };

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const solve = (state) => {
    const key = state.join(',');
    if (memo.has(key)) return memo.get(key);
    if (state.every((count) => count === 0)) return 0;

    let best = Infinity;

    for (let mask = 1; mask < (1 << 5); mask += 1) {
      let groupSize = 0;
      let valid = true;

      for (let i = 0; i < 5; i += 1) {
        if (mask & (1 << i)) {
          if (state[i] === 0) {
            valid = false;
            break;
          }
          groupSize += 1;
        }
      }

      if (!valid) continue;

      const next = state.map((count, i) => count - ((mask >> i) & 1));
      next.sort((a, b) => b - a);

      best = Math.min(best, GROUP_PRICE[groupSize] + solve(next));
    }

    memo.set(key, best);
    return best;
  };

  return solve(counts.sort((a, b) => b - a));
};
