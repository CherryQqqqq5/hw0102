//
// This is only a SKELETON file for the 'Sum Of Multiples' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

export const sum = (factors, level) => {
  const multiples = new Set();

  for (const factor of factors) {
    // A factor of 0 (or a negative one) contributes no positive multiples below level.
    if (factor <= 0) {
      continue;
    }
    for (let multiple = factor; multiple < level; multiple += factor) {
      multiples.add(multiple);
    }
  }

  let total = 0;
  for (const multiple of multiples) {
    total += multiple;
  }
  return total;
};
