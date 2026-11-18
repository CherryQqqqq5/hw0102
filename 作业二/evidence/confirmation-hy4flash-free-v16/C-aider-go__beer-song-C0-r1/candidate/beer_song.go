package beer

import (
	"errors"
	"fmt"
	"strings"
)

// A small count helper removes most wording duplication while leaving the three
// lyrical variants explicit and readable; polymorphism would add complexity here.
const maxBottles = 99

func Song() string {
	song, _ := Verses(maxBottles, 0)
	return song
}

func Verses(start, stop int) (string, error) {
	if start < 0 || stop < 0 || start > maxBottles || stop > maxBottles || start < stop {
		return "", errors.New("invalid verse range")
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

func Verse(n int) (string, error) {
	if n < 0 || n > maxBottles {
		return "", errors.New("invalid verse")
	}

	switch n {
	case 0:
		return fmt.Sprintf("No more bottles of beer on the wall, no more bottles of beer.\n"+
			"Go to the store and buy some more, %d bottles of beer on the wall.\n", maxBottles), nil
	case 1:
		return "1 bottle of beer on the wall, 1 bottle of beer.\n" +
			"Take it down and pass it around, no more bottles of beer on the wall.\n", nil
	default:
		return fmt.Sprintf("%[1]s of beer on the wall, %[1]s of beer.\n"+
			"Take one down and pass it around, %[2]s of beer on the wall.\n", bottles(n), bottles(n-1)), nil
	}
}

func bottles(n int) string {
	switch n {
	case 0:
		return "no more bottles"
	case 1:
		return "1 bottle"
	default:
		return fmt.Sprintf("%d bottles", n)
	}
}
