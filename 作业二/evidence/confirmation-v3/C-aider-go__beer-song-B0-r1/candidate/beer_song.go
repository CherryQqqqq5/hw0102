package beer

import (
	"fmt"
	"strings"
)

const maxBottles = 99

// bottleWord returns the correctly pluralized form of "bottle".
func bottleWord(n int) string {
	if n == 1 {
		return "bottle"
	}
	return "bottles"
}

// numberWord renders a bottle count as words when it is zero.
func numberWord(n int) string {
	if n == 0 {
		return "no more"
	}
	return fmt.Sprintf("%d", n)
}

// clause builds "<count> bottle(s) of beer".
func clause(n int) string {
	return fmt.Sprintf("%s %s of beer", numberWord(n), bottleWord(n))
}

// capitalize upper-cases the first letter of s.
func capitalize(s string) string {
	if s == "" {
		return s
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

// Verse returns a single verse of the song for the given number of bottles.
func Verse(n int) (string, error) {
	if n < 0 || n > maxBottles {
		return "", fmt.Errorf("invalid verse: %d bottles", n)
	}

	first := fmt.Sprintf("%s on the wall, %s.\n", capitalize(clause(n)), clause(n))

	var second string
	switch n {
	case 0:
		second = fmt.Sprintf("Go to the store and buy some more, %s on the wall.\n", clause(maxBottles))
	case 1:
		second = fmt.Sprintf("Take it down and pass it around, %s on the wall.\n", clause(0))
	default:
		second = fmt.Sprintf("Take one down and pass it around, %s on the wall.\n", clause(n-1))
	}

	return first + second, nil
}

// Verses returns the verses from start down to stop, separated by blank lines.
func Verses(start, stop int) (string, error) {
	if start < stop || start > maxBottles || stop < 0 {
		return "", fmt.Errorf("invalid verse range: %d..%d", start, stop)
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

// Song returns the complete lyrics of "99 Bottles of Beer".
func Song() string {
	song, err := Verses(maxBottles, 0)
	if err != nil {
		// The range is fixed and valid, so this cannot happen.
		panic(err)
	}
	return song
}
