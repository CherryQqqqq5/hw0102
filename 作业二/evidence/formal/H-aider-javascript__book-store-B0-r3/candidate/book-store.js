const GROUP_PRICES = [0, 800, 1520, 2160, 2560, 3000];

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const minCost = (state) => {
    const key = state.join(',');
    if (memo.has(key)) {
      return memo.get(key);
    }

    if (state.every((count) => count === 0)) {
      return 0;
    }

    let best = Infinity;

    for (let subset = 1; subset < 32; subset += 1) {
      const next = state.slice();
      let groupSize = 0;
      let possible = true;

      for (let i = 0; i < 5; i += 1) {
        if ((subset & (1 << i)) !== 0) {
          if (next[i] === 0) {
            possible = false;
            break;
          }
          next[i] -= 1;
          groupSize += 1;
        }
      }

      if (possible) {
        best = Math.min(best, GROUP_PRICES[groupSize] + minCost(next));
      }
    }

    memo.set(key, best);
    return best;
  };

  return minCost(counts);
};
