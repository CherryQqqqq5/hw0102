const GROUP_PRICE = [0, 800, 1520, 2160, 2560, 3000];

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const solve = (state) => {
    if (state.every((count) => count === 0)) {
      return 0;
    }

    const key = state.join(',');
    if (memo.has(key)) {
      return memo.get(key);
    }

    let best = Infinity;

    // Enumerate every non-empty subset of titles that can form one group.
    for (let mask = 1; mask < (1 << 5); mask += 1) {
      const next = state.slice();
      let groupSize = 0;
      let possible = true;

      for (let i = 0; i < 5; i += 1) {
        if (mask & (1 << i)) {
          if (state[i] === 0) {
            possible = false;
            break;
          }
          groupSize += 1;
          next[i] -= 1;
        }
      }

      if (!possible) {
        continue;
      }

      best = Math.min(best, GROUP_PRICE[groupSize] + solve(next));
    }

    memo.set(key, best);
    return best;
  };

  return solve(counts);
};
