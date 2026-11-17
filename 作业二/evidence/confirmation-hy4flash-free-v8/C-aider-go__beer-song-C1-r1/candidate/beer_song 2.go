package beer

import (
	"fmt"
	"strings"
)

const maxBottles = 99

func Song() string {
	song, _ := Verses(maxBottles, 0)
	return song
}

func Verses(start, stop int) (string, error) {
	if !validBottleCount(start) || !validBottleCount(stop) {
		return "", fmt.Errorf("verse numbers must be between 0 and %d", maxBottles)
	}
	if start < stop {
		return "", fmt.Errorf("start must be greater than or equal to stop")
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
	if !validBottleCount(n) {
		return "", fmt.Errorf("verse number must be between 0 and %d", maxBottles)
	}

	next := bottles(nextCount(n))
	switch n {
	case 0:
		return fmt.Sprintf("No more bottles of beer on the wall, no more bottles of beer.\nGo to the store and buy some more, %s of beer on the wall.\n", next), nil
	case 1:
		return fmt.Sprintf("1 bottle of beer on the wall, 1 bottle of beer.\nTake it down and pass it around, %s of beer on the wall.\n", next), nil
	default:
		return fmt.Sprintf("%d bottles of beer on the wall, %d bottles of beer.\nTake one down and pass it around, %s of beer on the wall.\n", n, n, next), nil
	}
}

func nextCount(n int) int {
	if n == 0 {
		return maxBottles
	}
	return n - 1
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
