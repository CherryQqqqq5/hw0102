package beer

import (
	"fmt"
	"strings"
)

const maxBottles = 99

// Verse returns the verse of the song for the given number of bottles.
func Verse(n int) (string, error) {
	if n < 0 || n > maxBottles {
		return "", fmt.Errorf("verse %d is outside the valid range 0..%d", n, maxBottles)
	}

	switch n {
	case 0:
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n", nil
	case 1:
		return "1 bottle of beer on the wall, 1 bottle of beer.\n" +
			"Take it down and pass it around, no more bottles of beer on the wall.\n", nil
	default:
		return fmt.Sprintf(
			"%s of beer on the wall, %s of beer.\n"+
				"Take one down and pass it around, %s of beer on the wall.\n",
			describeBottles(n), describeBottles(n), describeBottles(n-1),
		), nil
	}
}

// Verses returns the verses from start down to stop, inclusive,
// separated by a blank line.
func Verses(start, stop int) (string, error) {
	if start < stop {
		return "", fmt.Errorf("start verse %d must be greater than or equal to stop verse %d", start, stop)
	}

	var verses []string
	for n := start; n >= stop; n-- {
		verse, err := Verse(n)
		if err != nil {
			return "", err
		}
		verses = append(verses, verse)
	}
	return strings.Join(verses, "\n") + "\n", nil
}

// Song returns the entire "99 Bottles of Beer" song.
func Song() string {
	song, err := Verses(maxBottles, 0)
	if err != nil {
		panic(err) // unreachable: both arguments are always valid
	}
	return song
}

func describeBottles(n int) string {
	switch n {
	case 0:
		return "no more bottles"
	case 1:
		return "1 bottle"
	default:
		return fmt.Sprintf("%d bottles", n)
	}
}
