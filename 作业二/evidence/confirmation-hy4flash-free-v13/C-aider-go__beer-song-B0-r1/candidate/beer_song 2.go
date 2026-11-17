package beer

import (
	"errors"
	"fmt"
	"strings"
)

const maxBottles = 99

func Song() string {
	song, _ := Verses(maxBottles, 0)
	return song
}

func Verses(start, stop int) (string, error) {
	if start < 0 || stop < 0 || start > maxBottles || stop > maxBottles || start < stop {
		return "", errors.New("invalid verse range")
	}

	var lyrics strings.Builder
	for n := start; n >= stop; n-- {
		verse, err := Verse(n)
		if err != nil {
			return "", err
		}
		lyrics.WriteString(verse)
		lyrics.WriteByte('\n')
	}
	return lyrics.String(), nil
}

func Verse(n int) (string, error) {
	if n < 0 || n > maxBottles {
		return "", errors.New("invalid verse")
	}

	var verse strings.Builder
	verse.WriteString(initialBottlePhrase(n))
	verse.WriteString(" of beer on the wall, ")
	verse.WriteString(bottlePhrase(n))
	verse.WriteString(" of beer.\n")

	switch n {
	case 0:
		verse.WriteString("Go to the store and buy some more, 99 bottles of beer on the wall.\n")
	case 1:
		verse.WriteString("Take it down and pass it around, no more bottles of beer on the wall.\n")
	default:
		verse.WriteString("Take one down and pass it around, ")
		verse.WriteString(bottlePhrase(n - 1))
		verse.WriteString(" of beer on the wall.\n")
	}

	return verse.String(), nil
}

func bottlePhrase(n int) string {
	switch n {
	case 0:
		return "no more bottles"
	case 1:
		return "1 bottle"
	default:
		return fmt.Sprintf("%d bottles", n)
	}
}

func initialBottlePhrase(n int) string {
	if n == 0 {
		return "No more bottles"
	}
	return bottlePhrase(n)
}
