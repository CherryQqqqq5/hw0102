package beer

import (
	"fmt"
	"strings"
)

// Song returns the full lyrics of "99 Bottles of Beer on the Wall".
func Song() string {
	s, _ := Verses(99, 0)
	return s
}

// Verses returns the verses from start down to stop, inclusive.
func Verses(start, stop int) (string, error) {
	if start > 99 || start < 0 {
		return "", fmt.Errorf("start must be between 0 and 99")
	}
	if stop > 99 || stop < 0 {
		return "", fmt.Errorf("stop must be between 0 and 99")
	}
	if start < stop {
		return "", fmt.Errorf("start must not be less than stop")
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

// Verse returns a single verse of the song.
func Verse(n int) (string, error) {
	if n < 0 || n > 99 {
		return "", fmt.Errorf("verse must be between 0 and 99")
	}
	switch n {
	case 0:
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n", nil
	case 1:
		return "1 bottle of beer on the wall, 1 bottle of beer.\n" +
			"Take it down and pass it around, no more bottles of beer on the wall.\n", nil
	}
	return fmt.Sprintf("%[1]d bottles of beer on the wall, %[1]d bottles of beer.\n"+
		"Take one down and pass it around, %[2]d %[3]s of beer on the wall.\n", n, n-1, bottleWord(n-1)), nil
}

// bottleWord returns the singular or plural noun for a bottle count.
func bottleWord(n int) string {
	if n == 1 {
		return "bottle"
	}
	return "bottles"
}
