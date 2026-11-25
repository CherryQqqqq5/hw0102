const SUBJECTS = [
  'house that Jack built.',
  'malt',
  'rat',
  'cat',
  'dog',
  'cow with the crumpled horn',
  'maiden all forlorn',
  'man all tattered and torn',
  'priest all shaven and shorn',
  'rooster that crowed in the morn',
  'farmer sowing his corn',
  'horse and the hound and the horn',
];

const ACTIONS = [
  null,
  'that lay in',
  'that ate',
  'that killed',
  'that worried',
  'that tossed',
  'that milked',
  'that kissed',
  'that married',
  'that woke',
  'that kept',
  'that belonged to',
];

export class House {
  static verse(n) {
    if (n === 1) {
      return ['This is the house that Jack built.'];
    }
    const lines = [`This is the ${SUBJECTS[n - 1]}`];
    for (let i = n - 1; i >= 1; i -= 1) {
      lines.push(`${ACTIONS[i]} the ${SUBJECTS[i - 1]}`);
    }
    return lines;
  }

  static verses(start, end) {
    const result = [];
    for (let n = start; n <= end; n += 1) {
      if (n > start) {
        result.push('');
      }
      result.push(...House.verse(n));
    }
    return result;
  }
}
