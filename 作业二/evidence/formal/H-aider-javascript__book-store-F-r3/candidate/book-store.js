//
// This is only a SKELETON file for the 'BookStore' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

// Cost in cents of a single group of `size` different books.
const GROUP_COSTS = [0, 800, 1520, 2160, 2560, 3000];

export const cost = (books) => {
  const counts = [0, 0, 0, 0, 0];

  for (const book of books) {
    counts[book - 1] += 1;
  }

  const memo = new Map();

  const best = (state) => {
    const key = state.join(',');
    const cached = memo.get(key);

    if (cached !== undefined) {
      return cached;
    }

    if (state.every((count) => count === 0)) {
      return 0;
    }

    let result = Infinity;

    // Try every possible set of distinct titles to sell as one group.
    for (let mask = 1; mask < (1 << 5); mask += 1) {
      const next = state.slice();
      let size = 0;
      let valid = true;

      for (let i = 0; i < 5; i += 1) {
        if ((mask & (1 << i)) !== 0) {
          if (state[i] === 0) {
            valid = false;
            break;
          }

          next[i] -= 1;
          size += 1;
        }
      }

      if (valid) {
        result = Math.min(result, GROUP_COSTS[size] + best(next));
      }
    }

    memo.set(key, result);

    return result;
  };

  return best(counts);
};
