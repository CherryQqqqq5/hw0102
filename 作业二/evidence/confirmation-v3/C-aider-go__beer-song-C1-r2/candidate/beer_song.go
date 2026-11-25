package beer

import (
	"errors"
	"fmt"
	"strings"
)

const maxBottles = 99

// bottle returns the noun phrase for a given number of bottles,
// handling the singular form for one bottle.
func bottle(n int) string {
	if n == 1 {
		return "1 bottle of beer"
	}
	return fmt.Sprintf("%d bottles of beer", n)
}

func count(n int) string {
	if n == 0 {
		return "no more bottles of beer"
	}
	return bottle(n)
}

// Verse returns a single verse of the song.
func Verse(n int) (string, error) {
	if n < 0 || n > maxBottles {
		return "", errors.New("invalid verse number")
	}

	if n == 0 {
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n", nil
	}

	action := "Take one down and pass it around"
	if n == 1 {
		action = "Take it down and pass it around"
	}

	return fmt.Sprintf("%s on the wall, %s.\n%s, %s on the wall.\n",
		bottle(n), bottle(n), action, count(n-1)), nil
}

// Verses returns a range of verses, from start down to stop inclusive.
func Verses(start, stop int) (string, error) {
	if start < 0 || start > maxBottles || stop < 0 || stop > maxBottles || start < stop {
		return "", errors.New("invalid verse range")
	}

	verses := make([]string, 0, start-stop+1)
	for n := start; n >= stop; n-- {
		v, err := Verse(n)
		if err != nil {
			return "", err
		}
		verses = append(verses, v)
	}
	return strings.Join(verses, "\n") + "\n", nil
}

// Song returns the entire song.
func Song() string {
	song, _ := Verses(maxBottles, 0)
	return song
}
