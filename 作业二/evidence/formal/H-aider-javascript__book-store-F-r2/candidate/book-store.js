const BOOK_PRICE = 800;

const GROUP_PRICES = {
  0: 0,
  1: 800,
  2: 1520,
  3: 2160,
  4: 2560,
  5: 3000,
};

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

    let available = 0;
    for (let i = 0; i < 5; i += 1) {
      if (state[i] > 0) {
        available |= 1 << i;
      }
    }

    let best = Infinity;
    for (let subset = available; subset > 0; subset = (subset - 1) & available) {
      const next = state.slice();
      let groupSize = 0;

      for (let i = 0; i < 5; i += 1) {
        if ((subset & (1 << i)) !== 0) {
          next[i] -= 1;
          groupSize += 1;
        }
      }

      const total = GROUP_PRICES[groupSize] + solve(next);
      if (total < best) {
        best = total;
      }
    }

    memo.set(key, best);
    return best;
  };

  return solve(counts);
};
