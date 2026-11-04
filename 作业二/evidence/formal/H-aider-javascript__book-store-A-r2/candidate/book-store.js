const BOOK_PRICE = 800;
const DISCOUNT_PERCENT = [0, 0, 5, 10, 20, 25];

const groupCost = (size) =>
  (size * BOOK_PRICE * (100 - DISCOUNT_PERCENT[size])) / 100;

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const best = (state) => {
    if (state.every((n) => n === 0)) {
      return 0;
    }

    const key = state.join(',');
    if (memo.has(key)) {
      return memo.get(key);
    }

    let min = Infinity;
    // Try every non-empty subset of distinct books as one group.
    for (let mask = 1; mask < 32; mask += 1) {
      let size = 0;
      const next = state.slice();
      let valid = true;
      for (let i = 0; i < 5; i += 1) {
        if (mask & (1 << i)) {
          if (state[i] === 0) {
            valid = false;
            break;
          }
          next[i] -= 1;
          size += 1;
        }
      }
      if (valid) {
        min = Math.min(min, groupCost(size) + best(next));
      }
    }

    memo.set(key, min);
    return min;
  };

  return best(counts);
};
