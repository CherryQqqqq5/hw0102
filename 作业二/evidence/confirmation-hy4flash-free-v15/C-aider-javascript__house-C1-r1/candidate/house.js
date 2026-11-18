const SUBJECTS = [
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

const RELATIVE_PHRASES = [
  null,
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

const FIRST_VERSE = 1;
const LAST_VERSE = SUBJECTS.length - 1;

function validateVerse(verseNumber) {
  if (!Number.isInteger(verseNumber) || verseNumber < FIRST_VERSE || verseNumber > LAST_VERSE) {
    throw new RangeError(`Verse number must be an integer between ${FIRST_VERSE} and ${LAST_VERSE}`);
  }
}

export class House {
  static verse(verseNumber) {
    validateVerse(verseNumber);

    const lyrics = [`This is ${SUBJECTS[verseNumber]}`];

    for (let number = verseNumber; number >= 2; number -= 1) {
      lyrics.push(`${RELATIVE_PHRASES[number]} ${SUBJECTS[number - 1]}`);
    }

    return lyrics;
  }

  static verses(startVerse, endVerse) {
    validateVerse(startVerse);
    validateVerse(endVerse);

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
