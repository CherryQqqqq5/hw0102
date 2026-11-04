// Book Store exercise: compute the cheapest price (in cents) for a basket.
// One copy of any book costs 800 cents; groups of distinct titles get
// 5%, 10%, 20%, 25% discounts for 2, 3, 4, 5 different books respectively.

const BOOK_PRICE = 800;

// Discount rate applied to each book in a set of `size` distinct titles.
const discountFor = (size) => {
  switch (size) {
    case 5:
      return 0.25;
    case 4:
      return 0.2;
    case 3:
      return 0.1;
    case 2:
      return 0.05;
    default:
      return 0;
  }
};

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
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
    // Try every group size; identities of books within a group don't matter,
    // so always consume the `size` most frequent remaining titles.
    for (let size = 5; size >= 1; size -= 1) {
      if (sorted[size - 1] > 0) {
        const next = sorted
          .map((count, index) => (index < size ? count - 1 : count))
          .sort((a, b) => b - a);
        const groupCost = Math.round(size * BOOK_PRICE * (1 - discountFor(size)));
        const total = groupCost + cheapest(next);
        if (total < best) {
          best = total;
        }
      }
    }

    memo.set(key, best);
    return best;
  };

  return cheapest(counts);
};
