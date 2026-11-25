package beer

import (
	"fmt"
	"strings"
)

// maxBottles is the number of bottles at the start of the song.
const maxBottles = 99

// Verse returns a single verse of the song, or an error when n is out of range.
func Verse(n int) (string, error) {
	if n < 0 || n > maxBottles {
		return "", fmt.Errorf("invalid verse: %d", n)
	}

	var b strings.Builder
	switch n {
	case 0:
		b.WriteString("No more bottles of beer on the wall, no more bottles of beer.\n")
		b.WriteString("Go to the store and buy some more, 99 bottles of beer on the wall.\n")
	case 1:
		b.WriteString("1 bottle of beer on the wall, 1 bottle of beer.\n")
		b.WriteString("Take it down and pass it around, no more bottles of beer on the wall.\n")
	default:
		fmt.Fprintf(&b, "%d bottles of beer on the wall, %d bottles of beer.\n", n, n)
		if n == 2 {
			b.WriteString("Take one down and pass it around, 1 bottle of beer on the wall.\n")
		} else {
			fmt.Fprintf(&b, "Take one down and pass it around, %d bottles of beer on the wall.\n", n-1)
		}
	}
	return b.String(), nil
}

// Verses returns the verses from start down to stop, separated by blank lines.
func Verses(start, stop int) (string, error) {
	if start < stop || start < 0 || start > maxBottles || stop < 0 || stop > maxBottles {
		return "", fmt.Errorf("invalid verse range: %d to %d", start, stop)
	}

	var b strings.Builder
	for n := start; n >= stop; n-- {
		v, err := Verse(n)
		if err != nil {
			return "", err
		}
		b.WriteString(v)
		b.WriteString("\n")
	}
	return b.String(), nil
}

// Song returns the entire song.
func Song() string {
	song, _ := Verses(maxBottles, 0)
	return song
}
