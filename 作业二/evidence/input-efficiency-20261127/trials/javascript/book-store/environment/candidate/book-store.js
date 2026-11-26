const BOOK_PRICE_CENTS = 800;
const GROUP_PRICE_CENTS = [0, 800, 1520, 2160, 2560, 3000];

const normalize = (counts) => counts
  .filter((count) => count > 0)
  .sort((left, right) => right - left);

export const cost = (books) => {
  const countsById = new Map();

  for (const book of books) {
    countsById.set(book, (countsById.get(book) || 0) + 1);
  }

  const memo = new Map();

  const cheapest = (remaining) => {
    if (remaining.length === 0) {
      return 0;
    }

    const key = remaining.join(',');
    if (memo.has(key)) {
      return memo.get(key);
    }

    let best = remaining.reduce((total, count) => total + count * BOOK_PRICE_CENTS, 0);

    for (let size = 2; size <= Math.min(5, remaining.length); size += 1) {
      const next = remaining
        .map((count, index) => (index < size ? count - 1 : count));
      best = Math.min(best, GROUP_PRICE_CENTS[size] + cheapest(normalize(next)));
    }

    memo.set(key, best);
    return best;
  };

  return cheapest(normalize([...countsById.values()]));
};
