//
// This is only a SKELETON file for the 'Food Chain' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const animals = [
  { name: 'fly' },
  {
    name: 'spider',
    comment: 'It wriggled and jiggled and tickled inside her.',
    description: 'spider that wriggled and jiggled and tickled inside her',
  },
  { name: 'bird', comment: 'How absurd to swallow a bird!' },
  { name: 'cat', comment: 'Imagine that, to swallow a cat!' },
  { name: 'dog', comment: 'What a hog, to swallow a dog!' },
  { name: 'goat', comment: 'Just opened her throat and swallowed a goat!' },
  { name: 'cow', comment: "I don't know how she swallowed a cow!" },
  { name: 'horse', comment: "She's dead, of course!", last: true },
];

const REFRAIN = "I don't know why she swallowed the fly. Perhaps she'll die.";

function preyName(animal) {
  return animal.description || animal.name;
}

export class Song {
  verse(number) {
    const current = animals[number - 1];
    const lines = [`I know an old lady who swallowed a ${current.name}.`];

    if (current.last) {
      lines.push(current.comment);
      return `${lines.join('\n')}\n`;
    }

    if (current.comment) {
      lines.push(current.comment);
    }

    for (let i = number - 1; i >= 1; i -= 1) {
      lines.push(
        `She swallowed the ${animals[i].name} to catch the ${preyName(
          animals[i - 1]
        )}.`
      );
    }

    lines.push(REFRAIN);

    return `${lines.join('\n')}\n`;
  }

  verses(start, end) {
    const result = [];
    for (let number = start; number <= end; number += 1) {
      result.push(this.verse(number));
    }
    return `${result.join('\n')}\n`;
  }
}
