const BOOK_PRICE = 800;
const GROUP_PRICE = {
  1: 1 * BOOK_PRICE,
  2: 2 * BOOK_PRICE * 95 / 100,
  3: 3 * BOOK_PRICE * 90 / 100,
  4: 4 * BOOK_PRICE * 80 / 100,
  5: 5 * BOOK_PRICE * 75 / 100,
};

export const cost = (books) => {
  const counts = new Map();
  for (const book of books) {
    counts.set(book, (counts.get(book) || 0) + 1);
  }

  const memo = new Map();

  const best = (quantities) => {
    const sorted = quantities.filter((count) => count > 0).sort((a, b) => b - a);
    if (sorted.length === 0) {
      return 0;
    }

    const key = sorted.join(',');
    if (memo.has(key)) {
      return memo.get(key);
    }

    let minimum = Infinity;
    const maxGroupSize = Math.min(5, sorted.length);

    for (let size = 1; size <= maxGroupSize; size += 1) {
      const remaining = sorted.slice(size);
      for (let i = 0; i < size; i += 1) {
        remaining.push(sorted[i] - 1);
      }
      minimum = Math.min(minimum, GROUP_PRICE[size] + best(remaining));
    }

    memo.set(key, minimum);
    return minimum;
  };

  return best([...counts.values()]);
};
