package beer

import (
	"errors"
	"fmt"
	"strings"
)

const maxVerseNumber = 99

// Song returns the entire "99 Bottles of Beer" song.
func Song() string {
	song, _ := Verses(maxVerseNumber, 0)
	return song
}

// Verses returns the verses from start down to stop, each followed by a
// blank line.
func Verses(start, stop int) (string, error) {
	if start < 0 || start > maxVerseNumber {
		return "", errors.New("start verse must be between 0 and 99")
	}
	if stop < 0 || stop > maxVerseNumber {
		return "", errors.New("stop verse must be between 0 and 99")
	}
	if start < stop {
		return "", errors.New("start verse must not come after stop verse")
	}

	verses := make([]string, 0, start-stop+1)
	for n := start; n >= stop; n-- {
		verse, err := Verse(n)
		if err != nil {
			return "", err
		}
		verses = append(verses, verse)
	}

	return strings.Join(verses, "\n") + "\n", nil
}

// Verse returns a single verse of the song.
func Verse(n int) (string, error) {
	if n < 0 || n > maxVerseNumber {
		return "", errors.New("verse must be between 0 and 99")
	}

	switch {
	case n == 0:
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n", nil
	case n == 1:
		return "1 bottle of beer on the wall, 1 bottle of beer.\n" +
			"Take it down and pass it around, no more bottles of beer on the wall.\n", nil
	case n == 2:
		return "2 bottles of beer on the wall, 2 bottles of beer.\n" +
			"Take one down and pass it around, 1 bottle of beer on the wall.\n", nil
	default:
		return fmt.Sprintf("%d bottles of beer on the wall, %d bottles of beer.\n"+
			"Take one down and pass it around, %d bottles of beer on the wall.\n",
			n, n, n-1), nil
	}
}
