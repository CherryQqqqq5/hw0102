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

  return [...multiples].reduce((total, multiple) => total + multiple, 0);
};
