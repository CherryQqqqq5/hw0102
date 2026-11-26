export class Binary {
  constructor(binaryString) {
    this.binaryString = binaryString;
  }

  toDecimal() {
    const binaryString = this.binaryString;

    if (typeof binaryString !== 'string' || binaryString.length === 0) {
      return null;
    }

    let decimal = 0;

    for (const digit of binaryString) {
      if (digit !== '0' && digit !== '1') {
        return null;
      }

      decimal = decimal * 2 + (digit === '1' ? 1 : 0);
    }

    return decimal;
  }
}
