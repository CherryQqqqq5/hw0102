const PARTS = [
  null,
  { subject: 'house that Jack built.', action: null },
  { subject: 'malt', action: 'lay in the house that Jack built.' },
  { subject: 'rat', action: 'ate the malt' },
  { subject: 'cat', action: 'killed the rat' },
  { subject: 'dog', action: 'worried the cat' },
  { subject: 'cow with the crumpled horn', action: 'tossed the dog' },
  { subject: 'maiden all forlorn', action: 'milked the cow with the crumpled horn' },
  { subject: 'man all tattered and torn', action: 'kissed the maiden all forlorn' },
  { subject: 'priest all shaven and shorn', action: 'married the man all tattered and torn' },
  { subject: 'rooster that crowed in the morn', action: 'woke the priest all shaven and shorn' },
  { subject: 'farmer sowing his corn', action: 'kept the rooster that crowed in the morn' },
  { subject: 'horse and the hound and the horn', action: 'belonged to the farmer sowing his corn' },
];

export class House {
  static verse(number) {
    if (!Number.isInteger(number) || number < 1 || number >= PARTS.length) {
      throw new RangeError('Verse number must be between 1 and 12');
    }

    const lyrics = [`This is the ${PARTS[number].subject}`];

    for (let current = number; current > 1; current -= 1) {
      lyrics.push(`that ${PARTS[current].action}`);
    }

    return lyrics;
  }

  static verses(start, end) {
    const lyrics = [];

    for (let number = start; number <= end; number += 1) {
      if (lyrics.length > 0) {
        lyrics.push('');
      }

      lyrics.push(...House.verse(number));
    }

    return lyrics;
  }
}
