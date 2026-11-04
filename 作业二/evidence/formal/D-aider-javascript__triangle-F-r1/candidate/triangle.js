//
// This is only a SKELETON file for the 'Triangle' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

export class Triangle {
  constructor(...sides) {
    this.sides = sides;
  }

  get isValid() {
    if (this.sides.length !== 3) {
      return false;
    }

    const [a, b, c] = this.sides;

    if (this.sides.some((side) => side <= 0)) {
      return false;
    }

    return a + b >= c && b + c >= a && a + c >= b;
  }

  get isEquilateral() {
    return this.isValid && this.sides.every((side) => side === this.sides[0]);
  }

  get isIsosceles() {
    if (!this.isValid) {
      return false;
    }

    const [a, b, c] = this.sides;

    return a === b || b === c || a === c;
  }

  get isScalene() {
    if (!this.isValid) {
      return false;
    }

    const [a, b, c] = this.sides;

    return a !== b && b !== c && a !== c;
  }
}
