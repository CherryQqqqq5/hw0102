//
// This is only a SKELETON file for the 'BookStore' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const BOOK_PRICE = 800;
const DISCOUNTS = [0, 1, 0.95, 0.9, 0.8, 0.75];

// Memoized search over the multiset of remaining copy counts.
// State is the counts of each distinct title, sorted descending so that
// permutations of the same multiset share a single cache entry.
const memo = new Map();

const bestPrice = (counts) => {
  if (counts.every((c) => c === 0)) return 0;

  const key = counts.join(',');
  if (memo.has(key)) return memo.get(key);

  let best = Infinity;
  // Choose which distinct titles (1..5 of them) to put in the next group.
  // All titles with a positive count are interchangeable for the purpose
  // of forming a group, so only the number of titles matters here.
  const available = counts.filter((c) => c > 0).length;

  for (let groupSize = 1; groupSize <= Math.min(5, available); groupSize += 1) {
    const next = counts.slice();
    for (let i = 0; i < groupSize; i += 1) next[i] -= 1;
    next.sort((a, b) => b - a);

    const groupCost = Math.round(groupSize * BOOK_PRICE * DISCOUNTS[groupSize]);
    best = Math.min(best, groupCost + bestPrice(next));
  }

  memo.set(key, best);
  return best;
};

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];
  books.forEach((book) => {
    counts[book - 1] += 1;
  });
  counts.sort((a, b) => b - a);
  return bestPrice(counts);
};
