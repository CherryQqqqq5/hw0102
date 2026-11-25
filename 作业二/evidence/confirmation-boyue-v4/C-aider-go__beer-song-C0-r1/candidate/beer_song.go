package beer

import (
	"fmt"
	"strings"
)

// The song runs over these verse numbers, from an empty wall (verse 0)
// all the way up to a full case of beer.
const (
	minBottles = 0
	maxBottles = 99
)

// Song returns the entire song, from 99 bottles down to the wall running
// dry and the restorative trip to the store.
func Song() string {
	song, _ := Verses(maxBottles, minBottles)
	return song
}

// Verses returns the verses from start down to stop, each followed by a
// blank line. It returns an error if either bound lies outside the
// range [0, 99] or if start is less than stop.
func Verses(start, stop int) (string, error) {
	if start > maxBottles || stop < minBottles || start < stop {
		return "", fmt.Errorf("invalid verse range [%d, %d]", start, stop)
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

// Verse returns a single verse of the song, including its trailing newline.
func Verse(n int) (string, error) {
	if n < minBottles || n > maxBottles {
		return "", fmt.Errorf("verse %d is outside the range [%d, %d]", n, minBottles, maxBottles)
	}

	// Verse 0 does not mention taking a bottle down at all.
	if n == 0 {
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n", nil
	}

	action := "Take one down and pass it around"
	if n == 1 {
		action = "Take it down and pass it around"
	}

	return fmt.Sprintf("%s, %s of beer.\n%s, %s.\n",
		onTheWall(n), bottles(n), action, onTheWall(n-1)), nil
}

// bottles spells out a count the way the song refers to it.
func bottles(n int) string {
	switch {
	case n == 1:
		return "1 bottle"
	case n == 0:
		return "no more bottles"
	default:
		return fmt.Sprintf("%d bottles", n)
	}
}

// onTheWall is a bottle count followed by "of beer on the wall".
func onTheWall(n int) string {
	return bottles(n) + " of beer on the wall"
}
