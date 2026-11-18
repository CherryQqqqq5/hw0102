const PHRASES = [
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
      `This is ${PHRASES[number - 1]}`,
      ...RELATIONS.slice(1, number).reverse(),
    ];
  }

  static verses(start, end) {
    const lyrics = [];

    for (let number = start; number <= end; number += 1) {
      if (number > start) {
        lyrics.push('');
      }
      lyrics.push(...House.verse(number));
    }

    return lyrics;
  }
}
