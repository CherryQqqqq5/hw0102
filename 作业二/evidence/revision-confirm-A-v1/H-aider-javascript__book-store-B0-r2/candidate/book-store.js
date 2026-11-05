//
// Book Store - calculates the price of a basket of books with group discounts.
//

// Price in cents for a group of `size` *different* books.
const GROUP_PRICE = {
  1: 800, // 1 x 800, no discount
  2: 1520, // 5% off
  3: 2160, // 10% off
  4: 2560, // 20% off
  5: 3000, // 25% off
};

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const solve = (state) => {
    const key = state.join(',');
    const cached = memo.get(key);
    if (cached !== undefined) return cached;

    // Position of the first (highest count) remaining book.
    const first = state.findIndex((c) => c > 0);
    if (first === -1) {
      memo.set(key, 0);
      return 0;
    }

    const available = [];
    for (let i = 0; i < state.length; i += 1) {
      if (state[i] > 0) available.push(i);
    }
    const others = available.filter((i) => i !== first);

    let best = Infinity;
    // Every group must include the first available book (avoids reordering
    // duplicated partitions); enumerate all subsets of the remaining titles.
    for (let mask = 0; mask < 1 << others.length; mask += 1) {
      const group = [first];
      for (let bit = 0; bit < others.length; bit += 1) {
        if (mask & (1 << bit)) group.push(others[bit]);
      }

      const next = state.slice();
      for (const index of group) next[index] -= 1;
      next.sort((a, b) => b - a);

      const total = GROUP_PRICE[group.length] + solve(next);
      if (total < best) best = total;
    }

    memo.set(key, best);
    return best;
  };

  return solve(counts.slice().sort((a, b) => b - a));
};
