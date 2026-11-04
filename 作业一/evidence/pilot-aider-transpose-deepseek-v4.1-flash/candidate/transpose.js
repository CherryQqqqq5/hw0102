//
// This is only a SKELETON file for the 'Transpose' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

export const transpose = (lines) => {
  if (!lines || lines.length === 0) {
    return [];
  }

  const maxLength = Math.max(...lines.map((line) => line.length));
  const result = [];

  for (let col = 0; col < maxLength; col++) {
    // Last row that actually has a character in this column. Anything after
    // that is filler and must not appear at the end of the transposed row.
    let last = -1;
    for (let row = 0; row < lines.length; row++) {
      if (lines[row].length > col) {
        last = row;
      }
    }

    let transposedRow = '';
    for (let row = 0; row <= last; row++) {
      transposedRow +=
        col < lines[row].length ? lines[row][col] : ' ';
    }
    result.push(transposedRow);
  }

  return result;
};
