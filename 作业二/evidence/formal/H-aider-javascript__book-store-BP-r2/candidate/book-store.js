const BOOK_PRICE = 800;

const DISCOUNTS = {
  1: 0,
  2: 5,
  3: 10,
  4: 20,
  5: 25,
};

const groupCost = (size) => size * BOOK_PRICE * (100 - DISCOUNTS[size]) / 100;

export const cost = (books) => {
  if (books.length === 0) return 0;

  // Count how many copies of each distinct title are in the basket.
  const counts = new Map();
  for (const book of books) {
    counts.set(book, (counts.get(book) || 0) + 1);
  }

  // Build the greedy grouping: group sizes are determined by how many
  // titles have at least that many copies.
  const perTitle = [...counts.values()];
  const maxCopies = Math.max(...perTitle);
  const groupsBySize = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  for (let level = 1; level <= maxCopies; level += 1) {
    const size = perTitle.filter((c) => c >= level).length;
    groupsBySize[size] += 1;
  }

  // A group of five plus a group of three is always beaten by two groups
  // of four (25% + 10% vs 20% + 20%), so swap them pairwise.
  const swaps = Math.min(groupsBySize[5], groupsBySize[3]);
  groupsBySize[5] -= swaps;
  groupsBySize[3] -= swaps;
  groupsBySize[4] += 2 * swaps;

  // Any remaining group of 3 paired with a group of 5 is already handled;
  // other combinations (e.g. 3+3 vs 4+2) are covered by the greedy sizes.
  let total = 0;
  for (let size = 1; size <= 5; size += 1) {
    total += groupsBySize[size] * groupCost(size);
  }
  return total;
};
