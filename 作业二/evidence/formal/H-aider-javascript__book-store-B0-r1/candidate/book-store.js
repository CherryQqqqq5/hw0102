const BOOK_PRICE = 800;
const GROUP_PRICES = [0, 800, 1520, 2160, 2560, 3000];

export const cost = (books) => {
  const counts = Array(5).fill(0);
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const cheapest = (state) => {
    const sorted = [...state].sort((a, b) => b - a);
    if (sorted[0] === 0) {
      return 0;
    }

    const key = sorted.join(',');
    if (memo.has(key)) {
      return memo.get(key);
    }

    let best = Infinity;

    // Try every possible group of distinct titles.
    for (let mask = 1; mask < 1 << 5; mask += 1) {
      const next = [...sorted];
      let groupSize = 0;
      let valid = true;

      for (let i = 0; i < 5; i += 1) {
        if (mask & (1 << i)) {
          if (sorted[i] === 0) {
            valid = false;
            break;
          }
          next[i] -= 1;
          groupSize += 1;
        }
      }

      if (valid) {
        best = Math.min(best, GROUP_PRICES[groupSize] + cheapest(next));
      }
    }

    memo.set(key, best);
    return best;
  };

  return cheapest(counts);
};
