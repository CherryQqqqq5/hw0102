//
// House exercise implementation.
//

const NOUNS = [
  'house',
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

const VERBS = [
  null,
  'lay in',
  'ate',
  'killed',
  'worried',
  'tossed',
  'milked',
  'kissed',
  'married',
  'woke',
  'kept',
  'belonged to',
];

export class House {
  static verse(n) {
    if (n < 1 || n > NOUNS.length) {
      throw new Error('Verse must be between 1 and 12');
    }
    if (n === 1) {
      return ['This is the house that Jack built.'];
    }
    const lines = [`This is the ${NOUNS[n - 1]}`];
    for (let j = n - 1; j >= 1; j -= 1) {
      const suffix = j === 1 ? ' that Jack built.' : '';
      lines.push(`that ${VERBS[j]} the ${NOUNS[j - 1]}${suffix}`);
    }
    return lines;
  }

  static verses(start, end) {
    const result = [];
    for (let n = start; n <= end; n += 1) {
      if (result.length > 0) {
        result.push('');
      }
      result.push(...House.verse(n));
    }
    return result;
  }
}
