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
  'lay in',
  'ate',
  'killed',
  'worried',
  'tossed',
  'milked',
  'kissed',
  'married',
  'woke',
  'kept',
  'belonged to',
];

export class House {
  static verse(verseNumber) {
    const lines = [`This is ${subjects[verseNumber - 1]}`];

    for (let currentIndex = verseNumber - 1; currentIndex > 0; currentIndex -= 1) {
      const previousIndex = currentIndex - 1;
      lines.push(`that ${actions[previousIndex]} ${subjects[previousIndex]}`);
    }

    return lines;
  }

  static verses(startVerse, endVerse) {
    const lyrics = [];

    for (let verseNumber = startVerse; verseNumber <= endVerse; verseNumber += 1) {
      if (verseNumber > startVerse) {
        lyrics.push('');
      }

      lyrics.push(...House.verse(verseNumber));
    }

    return lyrics;
  }
}
