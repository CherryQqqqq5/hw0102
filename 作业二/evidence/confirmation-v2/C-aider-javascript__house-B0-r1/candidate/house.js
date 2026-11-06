//
// This is only a SKELETON file for the 'House' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const FIRST_LINES = [
  null,
  'This is the house that Jack built.',
  'This is the malt',
  'This is the rat',
  'This is the cat',
  'This is the dog',
  'This is the cow with the crumpled horn',
  'This is the maiden all forlorn',
  'This is the man all tattered and torn',
  'This is the priest all shaven and shorn',
  'This is the rooster that crowed in the morn',
  'This is the farmer sowing his corn',
  'This is the horse and the hound and the horn',
];

const CLAUSES = [
  null,
  null,
  'that lay in the house that Jack built.',
  'that ate the malt',
  'that killed the rat',
  'that worried the cat',
  'that tossed the dog',
  'that milked the cow with the crumpled horn',
  'that kissed the maiden all forlorn',
  'that married the man all tattered and torn',
  'that woke the priest all shaven and shorn',
  'that kept the rooster that crowed in the morn',
  'that belonged to the farmer sowing his corn',
];

export class House {
  static verse(number) {
    const lines = [FIRST_LINES[number]];
    for (let i = number; i >= 2; i -= 1) {
      lines.push(CLAUSES[i]);
    }
    return lines;
  }

  static verses(startVerse, endVerse) {
    const lines = [];
    for (let n = startVerse; n <= endVerse; n += 1) {
      if (n > startVerse) {
        lines.push('');
      }
      lines.push(...House.verse(n));
    }
    return lines;
  }
}
