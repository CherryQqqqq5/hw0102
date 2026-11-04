//
// This is only a SKELETON file for the 'Triangle' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

export class Triangle {
  constructor(...sides) {
    this.sides = sides;
  }

  get isTriangle() {
    const [a, b, c] = this.sides;
    return (
      this.sides.length === 3 &&
      a > 0 && b > 0 && c > 0 &&
      a + b >= c &&
      b + c >= a &&
      a + c >= b
    );
  }

  get isEquilateral() {
    const [a, b, c] = this.sides;
    return this.isTriangle && a === b && b === c;
  }

  get isIsosceles() {
    const [a, b, c] = this.sides;
    return (
      this.isTriangle && (a === b || b === c || a === c)
    );
  }

  get isScalene() {
    const [a, b, c] = this.sides;
    return (
      this.isTriangle && a !== b && b !== c && a !== c
    );
  }
}
