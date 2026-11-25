package beer

import (
	"fmt"
	"strings"
)

const (
	maxBottles = 99

	// standardVerse covers every verse except 0 and 1.
	standardVerse = "%s of beer on the wall, %s of beer.\n" +
		"Take one down and pass it around, %s of beer on the wall.\n"
	lastVerse = "No more bottles of beer on the wall, no more bottles of beer.\n" +
		"Go to the store and buy some more, 99 bottles of beer on the wall.\n"
	singleVerse = "%s of beer on the wall, %s of beer.\n" +
		"Take it down and pass it around, %s of beer on the wall.\n"
)

// bottles describes a number of bottles of beer, e.g. "1 bottle", "12 bottles".
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

// Verse returns the verse for n bottles of beer on the wall.
func Verse(n int) (string, error) {
	if n < 0 || n > maxBottles {
		return "", fmt.Errorf("invalid verse: %d bottles of beer", n)
	}

	switch n {
	case 0:
		return lastVerse, nil
	case 1:
		return fmt.Sprintf(singleVerse, bottles(1), bottles(1), bottles(0)), nil
	default:
		return fmt.Sprintf(standardVerse, bottles(n), bottles(n), bottles(n-1)), nil
	}
}

// Verses returns the verses from start bottles down to stop bottles.
func Verses(start, stop int) (string, error) {
	if start < stop || start > maxBottles || stop < 0 {
		return "", fmt.Errorf("invalid verse range: %d to %d", start, stop)
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

// Song returns the whole song, from 99 bottles down to none.
func Song() string {
	song, err := Verses(maxBottles, 0)
	if err != nil {
		panic(err)
	}
	return song
}
