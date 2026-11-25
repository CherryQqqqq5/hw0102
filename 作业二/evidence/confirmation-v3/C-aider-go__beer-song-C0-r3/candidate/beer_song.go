package beer

import (
	"fmt"
	"strings"
)

// Verse returns the single verse for the given number of bottles.
func Verse(n int) (string, error) {
	if n < 0 || n > 99 {
		return "", fmt.Errorf("invalid verse number: %d", n)
	}

	var b strings.Builder
	switch n {
	case 0:
		b.WriteString("No more bottles of beer on the wall, no more bottles of beer.\n")
		b.WriteString("Go to the store and buy some more, 99 bottles of beer on the wall.\n")
	case 1:
		b.WriteString("1 bottle of beer on the wall, 1 bottle of beer.\n")
		b.WriteString("Take it down and pass it around, no more bottles of beer on the wall.\n")
	case 2:
		b.WriteString("2 bottles of beer on the wall, 2 bottles of beer.\n")
		b.WriteString("Take one down and pass it around, 1 bottle of beer on the wall.\n")
	default:
		fmt.Fprintf(&b, "%d bottles of beer on the wall, %d bottles of beer.\n", n, n)
		fmt.Fprintf(&b, "Take one down and pass it around, %d bottles of beer on the wall.\n", n-1)
	}
	return b.String(), nil
}

// Verses returns all verses from start down to stop, separated by a blank line.
func Verses(start, stop int) (string, error) {
	if start < 0 || start > 99 || stop < 0 || stop > 99 || start < stop {
		return "", fmt.Errorf("invalid verse range: %d-%d", start, stop)
	}

	verses := make([]string, 0, start-stop+1)
	for n := start; n >= stop; n-- {
		v, err := Verse(n)
		if err != nil {
			return "", err
		}
		verses = append(verses, v)
	}
	return strings.Join(verses, "\n") + "\n", nil
}

// Song returns the entire song, from 99 bottles down to none.
func Song() string {
	s, err := Verses(99, 0)
	if err != nil {
		panic(err)
	}
	return s
}
