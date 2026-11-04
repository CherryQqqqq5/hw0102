//
// This is only a SKELETON file for the 'Food Chain' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const ANIMALS = [
  'fly',
  'spider',
  'bird',
  'cat',
  'dog',
  'goat',
  'cow',
  'horse',
];

const DESCRIPTIONS = {
  spider: 'It wriggled and jiggled and tickled inside her.',
  bird: 'How absurd to swallow a bird!',
  cat: 'Imagine that, to swallow a cat!',
  dog: 'What a hog, to swallow a dog!',
  goat: 'Just opened her throat and swallowed a goat!',
  cow: "I don't know how she swallowed a cow!",
};

const SPIDER_CLAUSE = ' that wriggled and jiggled and tickled inside her';

function preyPhrase(index) {
  return ANIMALS[index] + (ANIMALS[index] === 'spider' ? SPIDER_CLAUSE : '');
}

export class Song {
  verse(number) {
    const animal = ANIMALS[number - 1];
    const lines = [`I know an old lady who swallowed a ${animal}.`];

    if (animal === 'horse') {
      lines.push("She's dead, of course!");
      return lines.join('\n') + '\n';
    }

    if (DESCRIPTIONS[animal]) {
      lines.push(DESCRIPTIONS[animal]);
    }

    for (let i = number - 1; i >= 1; i -= 1) {
      lines.push(
        `She swallowed the ${ANIMALS[i]} to catch the ${preyPhrase(i - 1)}.`,
      );
    }

    lines.push("I don't know why she swallowed the fly. Perhaps she'll die.");
    return lines.join('\n') + '\n';
  }

  verses(start, end) {
    const verses = [];
    for (let i = start; i <= end; i += 1) {
      verses.push(this.verse(i));
    }
    return verses.join('\n') + '\n';
  }
}
