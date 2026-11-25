//
// Sum Of Multiples
//
// For each base value, find all multiples of that value that are strictly
// less than the level, combine them (deduplicating), and sum the result.
//

export const sum = (factors, level) => {
  const multiples = new Set();

  for (const factor of factors) {
    if (factor <= 0) continue; // 0 and negatives contribute nothing

    for (let multiple = factor; multiple < level; multiple += factor) {
      multiples.add(multiple);
    }
  }

  let total = 0;
  for (const value of multiples) {
    total += value;
  }

  return total;
};
