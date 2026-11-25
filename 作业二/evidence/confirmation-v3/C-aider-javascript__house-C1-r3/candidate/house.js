const PIECES = [
  ['house that Jack built.', null],
  ['malt', 'lay in'],
  ['rat', 'ate'],
  ['cat', 'killed'],
  ['dog', 'worried'],
  ['cow with the crumpled horn', 'tossed'],
  ['maiden all forlorn', 'milked'],
  ['man all tattered and torn', 'kissed'],
  ['priest all shaven and shorn', 'married'],
  ['rooster that crowed in the morn', 'woke'],
  ['farmer sowing his corn', 'kept'],
  ['horse and the hound and the horn', 'belonged to'],
];

export class House {
  static verse(n) {
    const lines = [`This is the ${PIECES[n - 1][0]}`];
    for (let i = n - 1; i >= 1; i -= 1) {
      lines.push(`that ${PIECES[i][1]} the ${PIECES[i - 1][0]}`);
    }
    return lines;
  }

  static verses(start, end) {
    const out = [];
    for (let n = start; n <= end; n += 1) {
      if (n > start) out.push('');
      out.push(...House.verse(n));
    }
    return out;
  }
}
