export const sum = (factors, limit) => {
  let total = 0;

  for (let number = 1; number < limit; number += 1) {
    if (factors.some((factor) => factor !== 0 && number % factor === 0)) {
      total += number;
    }
  }

  return total;
};
