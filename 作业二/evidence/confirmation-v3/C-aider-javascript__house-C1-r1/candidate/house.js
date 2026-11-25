//
// This is only a SKELETON file for the 'House' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const PARTS = [
  null,
  { subject: 'house that Jack built.', clause: null },
  { subject: 'malt', clause: 'that lay in the house that Jack built.' },
  { subject: 'rat', clause: 'that ate the malt' },
  { subject: 'cat', clause: 'that killed the rat' },
  { subject: 'dog', clause: 'that worried the cat' },
  { subject: 'cow with the crumpled horn', clause: 'that tossed the dog' },
  { subject: 'maiden all forlorn', clause: 'that milked the cow with the crumpled horn' },
  { subject: 'man all tattered and torn', clause: 'that kissed the maiden all forlorn' },
  { subject: 'priest all shaven and shorn', clause: 'that married the man all tattered and torn' },
  { subject: 'rooster that crowed in the morn', clause: 'that woke the priest all shaven and shorn' },
  { subject: 'farmer sowing his corn', clause: 'that kept the rooster that crowed in the morn' },
  { subject: 'horse and the hound and the horn', clause: 'that belonged to the farmer sowing his corn' },
];

export class House {
  static verse(number) {
    if (!Number.isInteger(number) || number < 1 || number >= PARTS.length) {
      throw new Error('Invalid verse number');
    }

    if (number === 1) {
      return ['This is the house that Jack built.'];
    }

    const lines = [`This is the ${PARTS[number].subject}`];
    for (let i = number; i >= 2; i--) {
      lines.push(PARTS[i].clause);
    }
    return lines;
  }

  static verses(startVerse, endVerse) {
    const result = [];
    for (let i = startVerse; i <= endVerse; i++) {
      if (i > startVerse) {
        result.push('');
      }
      result.push(...House.verse(i));
    }
    return result;
  }
}
