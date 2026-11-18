package beer

import (
	"fmt"
	"strings"
)

const (
	minBottles = 0
	maxBottles = 99
)

// Song returns the complete song. The whole song is just a verse range, so
// there is no need to duplicate the lyrics here.
func Song() string {
	song, err := Verses(maxBottles, minBottles)
	if err != nil {
		return ""
	}
	return song
}

// Verses returns the verses from start down to stop, inclusive.
func Verses(start, stop int) (string, error) {
	if start < minBottles || start > maxBottles ||
		stop < minBottles || stop > maxBottles ||
		start < stop {
		return "", fmt.Errorf("invalid verse range: %d to %d", start, stop)
	}

	var song strings.Builder
	for n := start; n >= stop; n-- {
		verse, err := Verse(n)
		if err != nil {
			return "", err
		}
		song.WriteString(verse)
		song.WriteByte('\n')
	}
	return song.String(), nil
}

// Verse returns one verse. The variation is kept in small helpers rather than
// duplicating entire verses; for only three wording changes this is clearer
// than introducing polymorphism.
func Verse(n int) (string, error) {
	if n < minBottles || n > maxBottles {
		return "", fmt.Errorf("invalid verse: %d", n)
	}

	current := bottleCount(n)
	first := current
	if n == 0 {
		first = "No more bottles"
	}

	next := n - 1
	if next < minBottles {
		next = maxBottles
	}

	action := "Take one down and pass it around"
	switch n {
	case 0:
		action = "Go to the store and buy some more"
	case 1:
		action = "Take it down and pass it around"
	}

	return fmt.Sprintf(
		"%s of beer on the wall, %s of beer.\n%s, %s of beer on the wall.\n",
		first,
		current,
		action,
		bottleCount(next),
	), nil
}

func bottleCount(n int) string {
	switch n {
	case 0:
		return "no more bottles"
	case 1:
		return "1 bottle"
	default:
		return fmt.Sprintf("%d bottles", n)
	}
}
