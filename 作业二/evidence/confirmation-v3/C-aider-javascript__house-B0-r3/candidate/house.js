//
// This is only a SKELETON file for the 'House' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const subjects = [
  // index 0 is unused so verses are 1-based
  null,
  'the house that Jack built.',
  'the malt',
  'the rat',
  'the cat',
  'the dog',
  'the cow with the crumpled horn',
  'the maiden all forlorn',
  'the man all tattered and torn',
  'the priest all shaven and shorn',
  'the rooster that crowed in the morn',
  'the farmer sowing his corn',
  'the horse and the hound and the horn',
];

const clauses = [
  // clauses[i] is the line in verse i that begins with "that"
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
    if (number === 1) {
      return [`This is ${subjects[1]}`];
    }

    const lines = [`This is ${subjects[number]}`];
    for (let i = number; i >= 2; i -= 1) {
      lines.push(clauses[i]);
    }
    return lines;
  }

  static verses(startVerse, endVerse) {
    const result = [];
    for (let i = startVerse; i <= endVerse; i += 1) {
      if (i > startVerse) {
        result.push('');
      }
      result.push(...House.verse(i));
    }
    return result;
  }
}
