package alphametics

import (
	"fmt"
	"sort"
	"strings"
	"unicode"
)

var powersOfTen = [...]int64{
	1,
	10,
	100,
	1000,
	10000,
	100000,
	1000000,
	10000000,
	100000000,
	1000000000,
	10000000000,
	100000000000,
	1000000000000,
	10000000000000,
	100000000000000,
	1000000000000000,
	10000000000000000,
	100000000000000000,
	1000000000000000000,
}

func Solve(puzzle string) (map[string]int, error) {
	cleaned := strings.Map(func(r rune) rune {
		if unicode.IsSpace(r) {
			return -1
		}
		return r
	}, puzzle)

	parts := strings.Split(cleaned, "==")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return nil, fmt.Errorf("invalid puzzle: %q", puzzle)
	}

	addends := strings.Split(parts[0], "+")
	for _, word := range addends {
		if !validWord(word) {
			return nil, fmt.Errorf("invalid puzzle: %q", puzzle)
		}
	}
	result := parts[1]
	if !validWord(result) {
		return nil, fmt.Errorf("invalid puzzle: %q", puzzle)
	}

	coefficients := make(map[byte]int64)
	present := make(map[byte]bool)
	leading := make(map[byte]bool)

	for _, word := range addends {
		if err := addWord(word, 1, coefficients, present, leading); err != nil {
			return nil, err
		}
	}
	if err := addWord(result, -1, coefficients, present, leading); err != nil {
		return nil, err
	}

	letters := make([]byte, 0, len(present))
	for letter := range present {
		letters = append(letters, letter)
	}
	sort.Slice(letters, func(i, j int) bool { return letters[i] < letters[j] })
	if len(letters) > 10 {
		return nil, fmt.Errorf("no solution for puzzle: %q", puzzle)
	}

	assignment := make([]int, len(letters))
	used := [10]bool{}
	var solution map[string]int

	var search func(depth int)
	search = func(depth int) {
		if solution != nil {
			return
		}
		if depth == len(letters) {
			var total int64
			for i, letter := range letters {
				total += coefficients[letter] * int64(assignment[i])
			}
			if total == 0 {
				solution = make(map[string]int, len(letters))
				for i, letter := range letters {
					solution[string(letter)] = assignment[i]
				}
			}
			return
		}

		letter := letters[depth]
		for digit := 0; digit <= 9; digit++ {
			if used[digit] || (leading[letter] && digit == 0) {
				continue
			}
			used[digit] = true
			assignment[depth] = digit
			search(depth + 1)
			used[digit] = false
			if solution != nil {
				return
			}
		}
	}
	search(0)

	if solution == nil {
		return nil, fmt.Errorf("no solution for puzzle: %q", puzzle)
	}
	return solution, nil
}

func validWord(word string) bool {
	if word == "" {
		return false
	}
	for i := 0; i < len(word); i++ {
		if word[i] < 'A' || word[i] > 'Z' {
			return false
		}
	}
	return true
}

func addWord(word string, sign int64, coefficients map[byte]int64, present, leading map[byte]bool) error {
	if len(word) > len(powersOfTen) {
		return fmt.Errorf("word too long in puzzle: %q", word)
	}
	if len(word) > 1 {
		leading[word[0]] = true
	}
	for i := 0; i < len(word); i++ {
		letter := word[i]
		exponent := len(word) - 1 - i
		present[letter] = true
		coefficients[letter] += sign * powersOfTen[exponent]
	}
	return nil
}
