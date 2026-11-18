const SUBJECTS = [
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
    if (!Number.isInteger(number) || number < 1 || number > SUBJECTS.length) {
      throw new RangeError(`Verse ${number} is outside the rhyme.`);
    }

    const lyrics = [SUBJECTS[number - 1]];

    for (let current = number; current > 1; current -= 1) {
      lyrics.push(CLAUSES[current - 1]);
    }

    return lyrics;
  }

  static verses(startVerse, endVerse) {
    if (
      !Number.isInteger(startVerse)
      || !Number.isInteger(endVerse)
      || startVerse < 1
      || endVerse < startVerse
      || endVerse > SUBJECTS.length
    ) {
      throw new RangeError(`Verses ${startVerse} through ${endVerse} are outside the rhyme.`);
    }

    const lyrics = [];

    for (let number = startVerse; number <= endVerse; number += 1) {
      if (number > startVerse) {
        lyrics.push('');
      }

      lyrics.push(...House.verse(number));
    }

    return lyrics;
  }
}
