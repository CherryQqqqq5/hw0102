export const sum = (factors, limit) => {
  const multiples = new Set();

  for (const factor of factors) {
    if (factor <= 0) {
      continue;
    }

    for (let multiple = factor; multiple < limit; multiple += factor) {
      multiples.add(multiple);
    }
  }

  let total = 0;
  for (const multiple of multiples) {
    total += multiple;
  }

  return total;
};
