//
// This is only a SKELETON file for the 'Sum Of Multiples' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

export const sum = (factors, level) => {
  const multiples = new Set();

  for (const rawFactor of factors) {
    const factor = Math.abs(rawFactor);

    // A base value of 0 contributes nothing, and non-finite / non-positive
    // values cannot produce a meaningful set of multiples.
    if (!Number.isFinite(factor) || factor < 1) continue;

    for (let multiple = factor; multiple < level; multiple += factor) {
      multiples.add(multiple);
    }
  }

  return [...multiples].reduce((total, value) => total + value, 0);
};
