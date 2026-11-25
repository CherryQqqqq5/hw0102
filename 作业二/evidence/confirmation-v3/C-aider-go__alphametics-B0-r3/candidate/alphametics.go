package alphametics

import (
	"errors"
	"sort"
	"strings"
)

type columnLetter struct {
	letter byte
	coeff  int
}

func Solve(puzzle string) (map[string]int, error) {
	parts := strings.Split(puzzle, "==")
	if len(parts) != 2 {
		return nil, errors.New("puzzle must contain exactly one ==")
	}

	var addends []string
	for _, raw := range strings.Split(parts[0], "+") {
		word := strings.TrimSpace(raw)
		if word == "" {
			return nil, errors.New("empty addend")
		}
		addends = append(addends, word)
	}

	result := strings.TrimSpace(parts[1])
	if result == "" {
		return nil, errors.New("missing result")
	}

	maxLen := len(result)
	for _, word := range addends {
		if len(word) > maxLen {
			maxLen = len(word)
		}
	}

	leading := make(map[byte]bool)
	allWords := append(append([]string{}, addends...), result)
	for _, word := range allWords {
		if len(word) > 1 {
			leading[word[0]] = true
		}
	}

	// For each column, count how many times each addend letter contributes.
	columns := make([][]columnLetter, maxLen)
	for pos := 0; pos < maxLen; pos++ {
		counts := make(map[byte]int)
		for _, word := range addends {
			idx := len(word) - 1 - pos
			if idx >= 0 {
				counts[word[idx]]++
			}
		}
		for letter, coeff := range counts {
			columns[pos] = append(columns[pos], columnLetter{letter, coeff})
		}
		sort.Slice(columns[pos], func(i, j int) bool {
			return columns[pos][i].letter < columns[pos][j].letter
		})
	}

	assignments := make(map[byte]int)
	var used [10]bool

	var solveColumn func(pos, carry int) bool
	var tryColumnLetters func(pos, carry, idx, sum int, resultLetter byte) bool

	tryColumnLetters = func(pos, carry, idx, sum int, resultLetter byte) bool {
		if idx == len(columns[pos]) {
			digit := sum % 10
			nextCarry := sum / 10

			if resultLetter == 0 {
				if sum != 0 {
					return false
				}
				return solveColumn(pos+1, 0)
			}

			if value, ok := assignments[resultLetter]; ok {
				if value != digit {
					return false
				}
				return solveColumn(pos+1, nextCarry)
			}

			if used[digit] || (digit == 0 && leading[resultLetter]) {
				return false
			}

			assignments[resultLetter] = digit
			used[digit] = true
			if solveColumn(pos+1, nextCarry) {
				return true
			}
			delete(assignments, resultLetter)
			used[digit] = false
			return false
		}

		entry := columns[pos][idx]
		if value, ok := assignments[entry.letter]; ok {
			return tryColumnLetters(pos, carry, idx+1, sum+entry.coeff*value, resultLetter)
		}

		start := 0
		if leading[entry.letter] {
			start = 1
		}
		for digit := start; digit < 10; digit++ {
			if used[digit] {
				continue
			}
			assignments[entry.letter] = digit
			used[digit] = true
			if tryColumnLetters(pos, carry, idx+1, sum+entry.coeff*digit, resultLetter) {
				return true
			}
			delete(assignments, entry.letter)
			used[digit] = false
		}
		return false
	}

	solveColumn = func(pos, carry int) bool {
		if pos == maxLen {
			return carry == 0
		}

		var resultLetter byte
		if pos < len(result) {
			resultLetter = result[len(result)-1-pos]
		}
		return tryColumnLetters(pos, carry, 0, carry, resultLetter)
	}

	if !solveColumn(0, 0) {
		return nil, errors.New("no solution")
	}

	solution := make(map[string]int, len(assignments))
	for letter, digit := range assignments {
		solution[string(letter)] = digit
	}
	return solution, nil
}
