//
// This is only a SKELETON file for the 'House' exercise. It's been provided as a
// convenience to get you started writing code faster.
//

const SUBJECTS = [
  null,
  { subject: 'house that Jack built', action: null },
  { subject: 'malt', action: 'lay in' },
  { subject: 'rat', action: 'ate' },
  { subject: 'cat', action: 'killed' },
  { subject: 'dog', action: 'worried' },
  { subject: 'cow with the crumpled horn', action: 'tossed' },
  { subject: 'maiden all forlorn', action: 'milked' },
  { subject: 'man all tattered and torn', action: 'kissed' },
  { subject: 'priest all shaven and shorn', action: 'married' },
  { subject: 'rooster that crowed in the morn', action: 'woke' },
  { subject: 'farmer sowing his corn', action: 'kept' },
  { subject: 'horse and the hound and the horn', action: 'belonged to' },
];

export class House {
  static verse(n) {
    if (n === 1) return ['This is the house that Jack built.'];
    const lines = [`This is the ${SUBJECTS[n].subject}`];
    for (let i = n - 1; i >= 2; i -= 1) {
      lines.push(`that ${SUBJECTS[i + 1].action} the ${SUBJECTS[i].subject}`);
    }
    lines.push('that lay in the house that Jack built.');
    return lines;
  }

  static verses(start, end) {
    const result = [];
    for (let i = start; i <= end; i += 1) {
      if (i > start) result.push('');
      result.push(...House.verse(i));
    }
    return result;
  }
}
