package beer

import (
	"fmt"
	"strings"
)

// verse returns the single verse for the given number of bottles.
func verse(n int) string {
	switch n {
	case 0:
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n"
	case 1:
		return "1 bottle of beer on the wall, 1 bottle of beer.\n" +
			"Take it down and pass it around, no more bottles of beer on the wall.\n"
	case 2:
		return "2 bottles of beer on the wall, 2 bottles of beer.\n" +
			"Take one down and pass it around, 1 bottle of beer on the wall.\n"
	default:
		return fmt.Sprintf("%d bottles of beer on the wall, %d bottles of beer.\n"+
			"Take one down and pass it around, %d bottles of beer on the wall.\n",
			n, n, n-1)
	}
}

// Song returns the whole song from 99 bottles down to none.
func Song() string {
	s, _ := Verses(99, 0)
	return s
}

// Verses returns verses from start down to stop, each separated by a blank line.
func Verses(start, stop int) (string, error) {
	if start < 0 || start > 99 || stop < 0 || stop > 99 || start < stop {
		return "", fmt.Errorf("invalid verse range: %d..%d", start, stop)
	}

	vs := make([]string, 0, start-stop+1)
	for n := start; n >= stop; n-- {
		vs = append(vs, verse(n))
	}
	return strings.Join(vs, "\n") + "\n", nil
}

// Verse returns the verse for the given number of bottles.
func Verse(n int) (string, error) {
	if n < 0 || n > 99 {
		return "", fmt.Errorf("invalid verse: %d", n)
	}
	return verse(n), nil
}
