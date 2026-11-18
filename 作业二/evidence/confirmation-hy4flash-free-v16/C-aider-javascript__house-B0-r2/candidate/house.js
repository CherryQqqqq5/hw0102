const fragments = [
  'the house that Jack built.',
  'the malt\nthat lay in ',
  'the rat\nthat ate ',
  'the cat\nthat killed ',
  'the dog\nthat worried ',
  'the cow with the crumpled horn\nthat tossed ',
  'the maiden all forlorn\nthat milked ',
  'the man all tattered and torn\nthat kissed ',
  'the priest all shaven and shorn\nthat married ',
  'the rooster that crowed in the morn\nthat woke ',
  'the farmer sowing his corn\nthat kept ',
  'the horse and the hound and the horn\nthat belonged to ',
];

const phrase = (number) => {
  if (!Number.isInteger(number) || number < 1 || number > fragments.length) {
    throw new RangeError('Verse number must be between 1 and 12');
  }

  return number === 1
    ? fragments[0]
    : `${fragments[number - 1]}${phrase(number - 1)}`;
};

export class House {
  static verse(number) {
    return `This is ${phrase(number)}`.split('\n');
  }

  static verses(startVerse, endVerse) {
    const lyrics = [];

    for (let number = startVerse; number <= endVerse; number += 1) {
      if (lyrics.length > 0) {
        lyrics.push('');
      }

      lyrics.push(...House.verse(number));
    }

    return lyrics;
  }
}
