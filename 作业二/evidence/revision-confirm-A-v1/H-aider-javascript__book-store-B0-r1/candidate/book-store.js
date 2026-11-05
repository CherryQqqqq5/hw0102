//
// This is only a SKELETON file for the 'BookStore' exercise. It's been provided as a
// convenience to get you started writing code faster.
//
const BOOK_PRICE = 800;

// Percentage discount for a group of `size` distinct books.
const DISCOUNT = [0, 0, 5, 10, 20, 25];

const groupCost = (size) => (size * BOOK_PRICE * (100 - DISCOUNT[size])) / 100;

export const cost = (books) => {
  const counts = [1, 2, 3, 4, 5]
    .map((id) => books.filter((book) => book === id).length)
    .filter((count) => count > 0)
    .sort((a, b) => b - a);

  const memo = new Map();

  const solve = (state) => {
    if (state.length === 0) {
      return 0;
    }

    const key = state.join(',');
    if (memo.has(key)) {
      return memo.get(key);
    }

    let best = Infinity;
    const maxGroup = Math.min(5, state.length);

    for (let size = 1; size <= maxGroup; size += 1) {
      const next = state
        .map((count, index) => (index < size ? count - 1 : count))
        .filter((count) => count > 0)
        .sort((a, b) => b - a);

      best = Math.min(best, groupCost(size) + solve(next));
    }

    memo.set(key, best);
    return best;
  };

  return solve(counts);
};
