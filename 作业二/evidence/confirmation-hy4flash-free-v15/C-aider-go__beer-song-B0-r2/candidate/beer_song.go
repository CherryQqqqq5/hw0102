package beer

import (
	"errors"
	"fmt"
	"strings"
)

const (
	minVerse = 0
	maxVerse = 99
)

var errInvalidVerse = errors.New("verse must be between 0 and 99")

func Song() string {
	song, err := Verses(maxVerse, minVerse)
	if err != nil {
		return ""
	}
	return song
}

func Verses(start, stop int) (string, error) {
	if err := validateVerse(start); err != nil {
		return "", err
	}
	if err := validateVerse(stop); err != nil {
		return "", err
	}
	if start < stop {
		return "", errors.New("start verse must be greater than or equal to stop verse")
	}

	var builder strings.Builder
	for n := start; n >= stop; n-- {
		verse, err := Verse(n)
		if err != nil {
			return "", err
		}
		builder.WriteString(verse)
		builder.WriteByte('\n')
	}
	return builder.String(), nil
}

func Verse(n int) (string, error) {
	if err := validateVerse(n); err != nil {
		return "", err
	}

	if n == 0 {
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n", nil
	}

	count := bottleCount(n)
	nextCount := bottleCount(n - 1)
	action := "Take one down and pass it around"
	if n == 1 {
		action = "Take it down and pass it around"
	}

	return fmt.Sprintf("%s of beer on the wall, %s of beer.\n%s, %s of beer on the wall.\n",
		count, count, action, nextCount), nil
}

func validateVerse(n int) error {
	if n < minVerse || n > maxVerse {
		return errInvalidVerse
	}
	return nil
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
