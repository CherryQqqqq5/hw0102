package beer

import (
	"errors"
	"fmt"
	"strings"
)

const maxBottles = 99

func Song() string {
	song, err := Verses(maxBottles, 0)
	if err != nil {
		return ""
	}
	return song
}

func Verses(start, stop int) (string, error) {
	if !validBottleCount(start) || !validBottleCount(stop) || start < stop {
		return "", errors.New("invalid verse range")
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

func Verse(n int) (string, error) {
	if !validBottleCount(n) {
		return "", errors.New("invalid verse")
	}

	switch n {
	case 0:
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n", nil
	case 1:
		return "1 bottle of beer on the wall, 1 bottle of beer.\n" +
			"Take it down and pass it around, no more bottles of beer on the wall.\n", nil
	default:
		return fmt.Sprintf("%d bottles of beer on the wall, %d bottles of beer.\n"+
			"Take one down and pass it around, %s of beer on the wall.\n",
			n, n, bottles(n-1)), nil
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

func validBottleCount(n int) bool {
	return n >= 0 && n <= maxBottles
}
