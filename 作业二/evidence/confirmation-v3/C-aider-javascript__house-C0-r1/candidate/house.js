//
// This is only a SKELETON file for the 'House' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const SUBJECTS = [
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

// ACTION[i] describes what subject i (1-based, SUBJECTS[i]) did to SUBJECTS[i - 1].
const ACTION = [
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
    const lines = [`This is ${SUBJECTS[n - 1]}`];
    for (let i = n - 1; i >= 1; i -= 1) {
      lines.push(`${ACTION[i]} ${SUBJECTS[i - 1]}`);
    }
    return lines;
  }

  static verses(start = 1, end = SUBJECTS.length) {
    const lyrics = [];
    for (let n = start; n <= end; n += 1) {
      if (n > start) {
        lyrics.push('');
      }
      lyrics.push(...House.verse(n));
    }
    return lyrics;
  }
}
