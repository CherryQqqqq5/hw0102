const subjects = [
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

const actions = [
  '',
  'lay in the house that Jack built.',
  'ate the malt',
  'killed the rat',
  'worried the cat',
  'tossed the dog',
  'milked the cow with the crumpled horn',
  'kissed the maiden all forlorn',
  'married the man all tattered and torn',
  'woke the priest all shaven and shorn',
  'kept the rooster that crowed in the morn',
  'belonged to the farmer sowing his corn',
];

export class House {
  static verse(verseNumber) {
    if (!Number.isInteger(verseNumber)
      || verseNumber < 1
      || verseNumber > subjects.length) {
      throw new RangeError('Verse number must be between 1 and 12');
    }

    const lyrics = [`This is ${subjects[verseNumber - 1]}`];

    for (let index = verseNumber - 1; index >= 1; index -= 1) {
      lyrics.push(`that ${actions[index]}`);
    }

    return lyrics;
  }

  static verses(startVerse, endVerse) {
    const lyrics = [];

    for (let number = startVerse; number <= endVerse; number += 1) {
      if (number > startVerse) {
        lyrics.push('');
      }

      lyrics.push(...this.verse(number));
    }

    return lyrics;
  }
}
