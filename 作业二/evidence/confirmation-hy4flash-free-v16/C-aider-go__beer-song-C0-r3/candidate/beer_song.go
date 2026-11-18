package beer

import (
	"fmt"
	"strings"
)

// Song returns the complete lyrics from 99 bottles down to no more bottles.
func Song() string {
	song, err := Verses(99, 0)
	if err != nil {
		panic(err)
	}
	return song
}

// Verses returns the lyrics from start down through stop, separated by a blank line.
func Verses(start, stop int) (string, error) {
	if !validVerse(start) || !validVerse(stop) {
		return "", fmt.Errorf("verse numbers must be between 0 and 99")
	}
	if start < stop {
		return "", fmt.Errorf("start verse must not be less than stop verse")
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

// Verse returns the lyrics for a single verse.
func Verse(n int) (string, error) {
	if !validVerse(n) {
		return "", fmt.Errorf("verse number must be between 0 and 99, got %d", n)
	}

	switch n {
	case 0:
		return fmt.Sprintf(
			"%s of beer on the wall, %s of beer.\nGo to the store and buy some more, %s of beer on the wall.\n",
			openingBottleCount(n), bottleCount(n), bottleCount(99),
		), nil
	case 1:
		return fmt.Sprintf(
			"%s of beer on the wall, %s of beer.\nTake it down and pass it around, %s of beer on the wall.\n",
			openingBottleCount(n), bottleCount(n), bottleCount(n-1),
		), nil
	default:
		return fmt.Sprintf(
			"%s of beer on the wall, %s of beer.\nTake one down and pass it around, %s of beer on the wall.\n",
			openingBottleCount(n), bottleCount(n), bottleCount(n-1),
		), nil
	}
}

func validVerse(n int) bool {
	return n >= 0 && n <= 99
}

func openingBottleCount(n int) string {
	if n == 0 {
		return "No more bottles"
	}
	return bottleCount(n)
}

func bottleCount(n int) string {
	switch {
	case n == 0:
		return "no more bottles"
	case n == 1:
		return "1 bottle"
	default:
		return fmt.Sprintf("%d bottles", n)
	}
}
