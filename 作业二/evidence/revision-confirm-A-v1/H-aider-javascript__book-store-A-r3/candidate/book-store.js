//
// Book Store exercise: compute the cheapest price (in cents) for a basket of
// books from a 5-book series, applying the best possible set discounts.
//

const BOOK_PRICE = 800;
const BOOK_COUNT = 5;
// Price in cents for a group of n distinct books (n = 0..5).
const GROUP_PRICE = [
  0,
  1 * BOOK_PRICE,           // 0% off
  2 * BOOK_PRICE * 0.95,    //  5% off -> 1520
  3 * BOOK_PRICE * 0.90,    // 10% off -> 2160
  4 * BOOK_PRICE * 0.80,    // 20% off -> 2560
  5 * BOOK_PRICE * 0.75,    // 25% off -> 3000
];

export const cost = (books) => {
  // Tally how many copies of each title we have.
  const counts = new Array(BOOK_COUNT).fill(0);
  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const solve = (state) => {
    // Canonical ordering: only the multiset of counts matters.
    const sorted = [...state].sort((a, b) => b - a);
    const key = sorted.join(',');

    if (memo.has(key)) {
      return memo.get(key);
    }

    if (sorted[0] === 0) {
      memo.set(key, 0);
      return 0;
    }

    let best = Infinity;

    // Enumerate every non-empty subset of distinct titles to form one group.
    for (let mask = 1; mask < (1 << BOOK_COUNT); mask += 1) {
      const next = sorted.slice();
      let size = 0;
      let valid = true;

      for (let i = 0; i < BOOK_COUNT; i += 1) {
        if (mask & (1 << i)) {
          if (next[i] === 0) {
            valid = false;
            break;
          }
          next[i] -= 1;
          size += 1;
        }
      }

      if (!valid) {
        continue;
      }

      const candidate = GROUP_PRICE[size] + solve(next);
      if (candidate < best) {
        best = candidate;
      }
    }

    memo.set(key, best);
    return best;
  };

  return solve(counts);
};
