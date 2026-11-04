const GROUP_PRICES = [0, 800, 1520, 2160, 2560, 3000];

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const solve = (remaining) => {
    const key = remaining.join(',');
    if (memo.has(key)) {
      return memo.get(key);
    }

    if (remaining.every((count) => count === 0)) {
      return 0;
    }

    let best = Infinity;

    // Try every non-empty subset of distinct titles as one group.
    for (let mask = 1; mask < 32; mask += 1) {
      let groupSize = 0;
      let valid = true;
      const next = remaining.slice();

      for (let i = 0; i < 5; i += 1) {
        if (mask & (1 << i)) {
          groupSize += 1;
          if (next[i] === 0) {
            valid = false;
            break;
          }
          next[i] -= 1;
        }
      }

      if (!valid) {
        continue;
      }

      best = Math.min(best, GROUP_PRICES[groupSize] + solve(next));
    }

    memo.set(key, best);
    return best;
  };

  return solve(counts);
};
