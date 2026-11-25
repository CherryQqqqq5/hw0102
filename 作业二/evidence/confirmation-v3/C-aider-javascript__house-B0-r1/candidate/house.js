//
// This is only a SKELETON file for the 'House' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const SUBJECTS = [
  null,
  'house that Jack built',
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
  null,
  'lay in the',
  'ate the',
  'killed the',
  'worried the',
  'tossed the',
  'milked the',
  'kissed the',
  'married the',
  'woke the',
  'kept the',
  'belonged to the',
];

export class House {
  static verse(number) {
    if (number === 1) {
      return ['This is the house that Jack built.'];
    }

    const lines = [`This is the ${SUBJECTS[number]}`];
    for (let i = number; i >= 2; i -= 1) {
      const ending = i === 2 ? '.' : '';
      lines.push(`that ${ACTIONS[i]} ${SUBJECTS[i - 1]}${ending}`);
    }

    return lines;
  }

  static verses(start, end) {
    const lyrics = [];
    for (let i = start; i <= end; i += 1) {
      if (i > start) {
        lyrics.push('');
      }
      lyrics.push(...House.verse(i));
    }
    return lyrics;
  }
}
