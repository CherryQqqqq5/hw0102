export class Binary {
  constructor(binary) {
    this.binary = binary;
  }

  toDecimal() {
    if (typeof this.binary !== 'string' || this.binary.length === 0) {
      return null;
    }

    let decimal = 0;

    for (let index = 0; index < this.binary.length; index += 1) {
      const digit = this.binary[index];

      if (digit !== '0' && digit !== '1') {
        return null;
      }

      decimal *= 2;
      if (digit === '1') {
        decimal += 1;
      }
    }

    return decimal;
  }
}
