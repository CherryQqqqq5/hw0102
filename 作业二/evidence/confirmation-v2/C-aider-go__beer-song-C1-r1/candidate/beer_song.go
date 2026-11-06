package beer

import (
	"fmt"
	"strings"
)

func Song() string {
	s, _ := Verses(99, 0)
	return s
}

func Verses(start, stop int) (string, error) {
	if start < stop || start > 99 || stop < 0 {
		return "", fmt.Errorf("invalid verse range: %d to %d", start, stop)
	}
	var sb strings.Builder
	for n := start; n >= stop; n-- {
		v, err := Verse(n)
		if err != nil {
			return "", err
		}
		sb.WriteString(v)
		sb.WriteString("\n")
	}
	return sb.String(), nil
}

func Verse(n int) (string, error) {
	if n < 0 || n > 99 {
		return "", fmt.Errorf("invalid verse: %d", n)
	}
	switch n {
	case 0:
		return "No more bottles of beer on the wall, no more bottles of beer.\n" +
			"Go to the store and buy some more, 99 bottles of beer on the wall.\n", nil
	case 1:
		return "1 bottle of beer on the wall, 1 bottle of beer.\n" +
			"Take it down and pass it around, no more bottles of beer on the wall.\n", nil
	case 2:
		return "2 bottles of beer on the wall, 2 bottles of beer.\n" +
			"Take one down and pass it around, 1 bottle of beer on the wall.\n", nil
	default:
		return fmt.Sprintf("%d bottles of beer on the wall, %d bottles of beer.\n", n, n) +
			fmt.Sprintf("Take one down and pass it around, %d bottles of beer on the wall.\n", n-1), nil
	}
}
