//
// Book Store: compute the cheapest price (in cents) for a basket of books
// from a 5-book series, applying the best possible set of multi-book discounts.
//

const UNIT_PRICE = 800; // one copy of any book costs $8.00

// percentage discount applied to a group of N *different* books
const DISCOUNT_PERCENT = { 1: 0, 2: 5, 3: 10, 4: 20, 5: 25 };

// price in cents of a single group of `size` different books
const groupPrice = (size) => (size * UNIT_PRICE * (100 - DISCOUNT_PERCENT[size])) / 100;

// Books of a series are interchangeable, so a basket is fully described by how
// many copies of each title remain. Canonical form: counts sorted descending.
const canonicalKey = (counts) => counts.slice().sort((a, b) => b - a).join(',');

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const cheapest = (state) => {
    if (state.every((count) => count === 0)) {
      return 0;
    }

    const key = canonicalKey(state);
    if (memo.has(key)) {
      return memo.get(key);
    }

    // Indices of titles that still have at least one copy left.
    const present = [];
    state.forEach((count, index) => {
      if (count > 0) present.push(index);
    });

    let best = Infinity;
    // Try every non-empty group of distinct titles as the next set to sell.
    for (let mask = 1; mask < 1 << present.length; mask += 1) {
      const next = state.slice();
      let size = 0;
      for (let bit = 0; bit < present.length; bit += 1) {
        if (mask & (1 << bit)) {
          next[present[bit]] -= 1;
          size += 1;
        }
      }
      best = Math.min(best, groupPrice(size) + cheapest(next.sort((a, b) => b - a)));
    }

    memo.set(key, best);
    return best;
  };

  return cheapest(counts);
};
