// Prices are stored in cents so the calculation stays entirely in integers.
const GROUP_PRICES = [0, 800, 1520, 2160, 2560, 3000];

export const cost = (books) => {
  const countsByBook = new Map();

  for (const book of books) {
    countsByBook.set(book, (countsByBook.get(book) || 0) + 1);
  }

  // The five titles are interchangeable when finding the cheapest grouping,
  // so only their counts, sorted from most to least, matter.
  const counts = Array.from(countsByBook.values())
    .sort((a, b) => b - a)
    .concat([0, 0, 0, 0, 0]);
  const [largest, second, third, fourth, smallest] = counts;

  // The natural grouping fills groups from the rarest title upward.
  let groupsOfFive = smallest;
  let groupsOfFour = fourth - smallest;
  let groupsOfThree = third - fourth;
  const groupsOfTwo = second - third;
  const groupsOfOne = largest - second;

  // A group of five plus a group of three costs 3000 + 2160 = 5160 cents;
  // restructuring them as two groups of four costs only 2 * 2560 = 5120.
  const replacements = Math.min(groupsOfFive, groupsOfThree);
  groupsOfFive -= replacements;
  groupsOfThree -= replacements;
  groupsOfFour += 2 * replacements;

  return (
    groupsOfFive * GROUP_PRICES[5] +
    groupsOfFour * GROUP_PRICES[4] +
    groupsOfThree * GROUP_PRICES[3] +
    groupsOfTwo * GROUP_PRICES[2] +
    groupsOfOne * GROUP_PRICES[1]
  );
};
