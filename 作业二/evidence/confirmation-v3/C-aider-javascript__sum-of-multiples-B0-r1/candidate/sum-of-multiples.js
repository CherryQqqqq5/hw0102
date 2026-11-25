//
// This is only a SKELETON file for the 'Sum Of Multiples' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

export const sum = (factors, level) => {
  const multiples = new Set();

  for (const factor of factors) {
    if (factor <= 0) {
      continue;
    }

    for (let multiple = factor; multiple < level; multiple += factor) {
      multiples.add(multiple);
    }
  }

  return [...multiples].reduce((total, value) => total + value, 0);
};
