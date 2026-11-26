const BOOK_PRICE_IN_CENTS = 800;

// Price of buying the indicated number of different books together.
const GROUP_PRICES_IN_CENTS = [
  0,
  BOOK_PRICE_IN_CENTS,
  1520,
  2160,
  2560,
  3000,
];

// Counts are kept sorted from the most-copied title to the least-copied one.
// Since titles are interchangeable, some optimal group can always be formed
// from the titles with the most copies remaining.
const cheapestRemaining = (initialCounts) => {
  const memo = new Map();
  const stack = [initialCounts.slice()];

  while (stack.length > 0) {
    const counts = stack[stack.length - 1];
    const key = counts.join(',');

    if (memo.has(key)) {
      stack.pop();
    } else {
      const differentTitles = counts.filter((count) => count > 0).length;

      if (differentTitles === 0) {
        memo.set(key, 0);
        stack.pop();
      } else {
        const candidates = [];
        let needsChild = false;

        for (let size = 1; size <= differentTitles; size += 1) {
          const remaining = counts.slice();

          for (let index = 0; index < size; index += 1) {
            remaining[index] -= 1;
          }

          remaining.sort((left, right) => right - left);

          const childKey = remaining.join(',');
          candidates.push({ size, childKey });

          if (!memo.has(childKey)) {
            stack.push(remaining);
            needsChild = true;
          }
        }

        if (!needsChild) {
          let cheapest = Infinity;

          for (const { size, childKey } of candidates) {
            const price = GROUP_PRICES_IN_CENTS[size] + memo.get(childKey);

            if (price < cheapest) {
              cheapest = price;
            }
          }

          memo.set(key, cheapest);
          stack.pop();
        }
      }
    }
  }

  return memo.get(initialCounts.join(','));
};

export const cost = (books) => {
  const countsByTitle = new Map();

  for (const book of books) {
    countsByTitle.set(book, (countsByTitle.get(book) || 0) + 1);
  }

  const counts = Array.from(countsByTitle.values())
    .sort((left, right) => right - left);

  return cheapestRemaining(counts);
};
