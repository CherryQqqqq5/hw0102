package beer

import (
	"fmt"
	"strings"
)

const (
	minBottles = 0
	maxBottles = 99
)

// Song returns all 100 verses of the song, from 99 bottles down to none.
func Song() string {
	song, _ := Verses(maxBottles, minBottles)
	return song
}

// Verses returns the verses from start down to stop, inclusive, separated by
// blank lines. Both bounds must be valid bottle counts, and start must not be
// less than stop.
func Verses(start, stop int) (string, error) {
	if !validCount(start) || !validCount(stop) || start < stop {
		return "", fmt.Errorf("invalid verse range: %d to %d", start, stop)
	}

	var song strings.Builder
	for n := start; n >= stop; n-- {
		verse, err := Verse(n)
		if err != nil {
			return "", err
		}
		song.WriteString(verse)
		song.WriteString("\n")
	}
	return song.String(), nil
}

// Verse returns the verse for n bottles. Valid bottle counts are 0 through 99.
func Verse(n int) (string, error) {
	if !validCount(n) {
		return "", fmt.Errorf("invalid verse: %d", n)
	}

	action, remaining := "Take one down and pass it around", bottles(n-1)
	switch n {
	case minBottles:
		action, remaining = "Go to the store and buy some more", bottles(maxBottles)
	case 1:
		action = "Take it down and pass it around"
	}

	return fmt.Sprintf(
		"%s of beer on the wall, %s of beer.\n%s, %s of beer on the wall.\n",
		capitalizedBottles(n), bottles(n), action, remaining,
	), nil
}

func validCount(n int) bool {
	return minBottles <= n && n <= maxBottles
}

func bottles(n int) string {
	switch n {
	case minBottles:
		return "no more bottles"
	case 1:
		return "1 bottle"
	default:
		return fmt.Sprintf("%d bottles", n)
	}
}

func capitalizedBottles(n int) string {
	if n == minBottles {
		return "No more bottles"
	}
	return bottles(n)
}
