const NOUNS = [
  'house',
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

// CLAUSES[i] describes what NOUNS[i] did to the noun before it, for i >= 1.
const CLAUSES = [
  null,
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
  static verse(verseNumber) {
    if (!Number.isInteger(verseNumber) || verseNumber < 1 || verseNumber > NOUNS.length) {
      throw new RangeError(
        `Verse must be an integer between 1 and ${NOUNS.length}`,
      );
    }

    if (verseNumber === 1) {
      return ['This is the house that Jack built.'];
    }

    const lines = [`This is the ${NOUNS[verseNumber - 1]}`];
    for (let i = verseNumber - 1; i >= 1; i -= 1) {
      lines.push(CLAUSES[i]);
    }
    return lines;
  }

  static verses(startVerse, endVerse) {
    const lines = [];
    for (let v = startVerse; v <= endVerse; v += 1) {
      if (lines.length > 0) {
        lines.push('');
      }
      lines.push(...House.verse(v));
    }
    return lines;
  }
}
