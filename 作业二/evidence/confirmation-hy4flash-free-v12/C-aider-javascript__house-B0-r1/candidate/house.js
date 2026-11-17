const SUBJECTS = [
  'house that Jack built.',
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

const RELATIONS = [
  '',
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
    return [
      `This is the ${SUBJECTS[number - 1]}`,
      ...RELATIONS.slice(1, number).reverse(),
    ];
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
