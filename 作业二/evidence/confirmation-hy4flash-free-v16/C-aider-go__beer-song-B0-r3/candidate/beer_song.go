package beer

import (
	"fmt"
	"strings"
)

const maxBottles = 99

func Song() string {
	song, err := Verses(maxBottles, 0)
	if err != nil {
		panic(err)
	}
	return song
}

func Verses(start, stop int) (string, error) {
	if start < stop || start < 0 || start > maxBottles || stop < 0 || stop > maxBottles {
		return "", fmt.Errorf("invalid verse range: %d through %d", start, stop)
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
		return "", fmt.Errorf("invalid verse: %d", n)
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
			"%s of beer on the wall, %s of beer.\nTake one down and pass it around, %s of beer on the wall.\n",
			bottleCount(n),
			bottleCount(n),
			bottleCount(n-1),
		), nil
	}
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
