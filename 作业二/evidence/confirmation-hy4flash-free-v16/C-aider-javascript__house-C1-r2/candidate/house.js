const PARTS = [
  '',
  { subject: 'the house that Jack built.' },
  { subject: 'the malt', verb: 'that lay in' },
  { subject: 'the rat', verb: 'that ate' },
  { subject: 'the cat', verb: 'that killed' },
  { subject: 'the dog', verb: 'that worried' },
  { subject: 'the cow with the crumpled horn', verb: 'that tossed' },
  { subject: 'the maiden all forlorn', verb: 'that milked' },
  { subject: 'the man all tattered and torn', verb: 'that kissed' },
  { subject: 'the priest all shaven and shorn', verb: 'that married' },
  { subject: 'the rooster that crowed in the morn', verb: 'that woke' },
  { subject: 'the farmer sowing his corn', verb: 'that kept' },
  { subject: 'the horse and the hound and the horn', verb: 'that belonged to' },
];

export class House {
  static verse(number) {
    const lines = [`This is ${PARTS[number].subject}`];

    for (let current = number - 1; current >= 2; current -= 1) {
      lines.push(`${PARTS[current + 1].verb} ${PARTS[current].subject}`);
    }

    if (number > 1) {
      lines.push(`${PARTS[2].verb} ${PARTS[1].subject}`);
    }

    return lines;
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
