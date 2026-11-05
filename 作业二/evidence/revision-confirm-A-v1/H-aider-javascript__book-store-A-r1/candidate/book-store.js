//
// This is only a SKELETON file for the 'BookStore' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

export const cost = (books) => {
  const counts = new Map();
  books.forEach((book) => {
    counts.set(book, (counts.get(book) || 0) + 1);
  });

  const groups = [];
  while ([...counts.values()].some((count) => count > 0)) {
    let groupSize = 0;
    for (const [book, count] of counts.entries()) {
      if (count > 0) {
        groupSize += 1;
        counts.set(book, count - 1);
      }
    }
    groups.push(groupSize);
  }

  const groupCounts = [0, 0, 0, 0, 0, 0];
  groups.forEach((size) => {
    groupCounts[size] += 1;
  });

  // A group of five plus a group of three can always be regrouped into
  // two groups of four for a larger discount.
  const replaced = Math.min(groupCounts[5], groupCounts[3]);
  groupCounts[5] -= replaced;
  groupCounts[3] -= replaced;
  groupCounts[4] += 2 * replaced;

  const prices = [0, 800, 1520, 2160, 2560, 3000];
  return groupCounts.reduce(
    (total, count, size) => total + count * prices[size],
    0
  );
};
