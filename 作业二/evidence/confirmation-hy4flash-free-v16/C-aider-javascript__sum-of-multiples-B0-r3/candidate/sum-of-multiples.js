export const sum = (factors, limit) => {
  const multiples = new Set();

  for (const factor of factors) {
    if (factor === 0) {
      continue;
    }

    const step = Math.abs(factor);
    for (let multiple = step; multiple < limit; multiple += step) {
      multiples.add(multiple);
    }
  }

  let total = 0;
  for (const multiple of multiples) {
    total += multiple;
  }

  return total;
};
