package beer

import (
	"fmt"
	"strings"
)

const (
	minBottles = 0
	maxBottles = 99
)

// bottleCount returns the phrase describing n bottles, e.g. "1 bottle".
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

// Verse returns verse n of the song.
func Verse(n int) (string, error) {
	if n < minBottles || n > maxBottles {
		return "", fmt.Errorf("invalid verse: %d", n)
	}

	var b strings.Builder
	if n == 0 {
		b.WriteString("No more bottles of beer on the wall, no more bottles of beer.\n")
		b.WriteString("Go to the store and buy some more, 99 bottles of beer on the wall.\n")
		return b.String(), nil
	}

	if n == 1 {
		b.WriteString("1 bottle of beer on the wall, 1 bottle of beer.\n")
		b.WriteString("Take it down and pass it around, no more bottles of beer on the wall.\n")
		return b.String(), nil
	}

	fmt.Fprintf(&b, "%d bottles of beer on the wall, %d bottles of beer.\n", n, n)
	fmt.Fprintf(&b, "Take one down and pass it around, %s of beer on the wall.\n", bottleCount(n-1))
	return b.String(), nil
}

// Verses returns verses from start down to stop, separated by a blank line.
func Verses(start, stop int) (string, error) {
	if start < minBottles || start > maxBottles {
		return "", fmt.Errorf("invalid start verse: %d", start)
	}
	if stop < minBottles || stop > maxBottles {
		return "", fmt.Errorf("invalid stop verse: %d", stop)
	}
	if start < stop {
		return "", fmt.Errorf("start verse %d is less than stop verse %d", start, stop)
	}

	var verses []string
	for n := start; n >= stop; n-- {
		v, err := Verse(n)
		if err != nil {
			return "", err
		}
		verses = append(verses, v)
	}
	return strings.Join(verses, "\n") + "\n", nil
}

// Song returns the whole song, from 99 bottles down to none.
func Song() string {
	s, err := Verses(maxBottles, minBottles)
	if err != nil {
		panic(err)
	}
	return s
}
