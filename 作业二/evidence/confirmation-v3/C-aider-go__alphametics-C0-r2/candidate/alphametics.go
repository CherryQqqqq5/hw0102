package alphametics

import (
	"errors"
	"strings"
	"unicode"
)

type columnCounts map[byte]int

type puzzleSpec struct {
	addends []string
	result  string
	leading map[byte]bool
}

func parsePuzzle(puzzle string) (*puzzleSpec, error) {
	sides := strings.Split(puzzle, "==")
	if len(sides) != 2 {
		return nil, errors.New("puzzle must contain exactly one ==")
	}

	clean := func(s string) string {
		return strings.Map(func(r rune) rune {
			if unicode.IsSpace(r) {
				return -1
			}
			return r
		}, s)
	}

	p := &puzzleSpec{leading: make(map[byte]bool)}
	for _, addend := range strings.Split(sides[0], "+") {
		word := clean(addend)
		if word == "" {
			return nil, errors.New("empty addend")
		}
		p.addends = append(p.addends, word)
	}
	p.result = clean(sides[1])
	if p.result == "" {
		return nil, errors.New("empty result")
	}

	for _, word := range append(append([]string(nil), p.addends...), p.result) {
		if len(word) > 1 {
			p.leading[word[0]] = true
		}
	}
	return p, nil
}

// Solve returns the unique digit assignment for the alphametics puzzle, or an
// error if the puzzle has no solution.
func Solve(puzzle string) (map[string]int, error) {
	p, err := parsePuzzle(puzzle)
	if err != nil {
		return nil, err
	}

	maxLen := len(p.result)
	for _, word := range p.addends {
		if len(word) > maxLen {
			maxLen = len(word)
		}
	}

	assigned := make(map[byte]int)
	var used [10]bool
	var solution map[byte]int

	var search func(column, carry int) bool
	search = func(column, carry int) bool {
		if column == maxLen {
			if carry != 0 {
				return false
			}
			solution = make(map[byte]int, len(assigned))
			for letter, digit := range assigned {
				solution[letter] = digit
			}
			return true
		}

		addCounts := make(columnCounts)
		var unassigned []byte
		seen := make(map[byte]bool)

		addLetter := func(letter byte, count bool) {
			if count {
				addCounts[letter]++
			}
			if _, ok := assigned[letter]; !ok && !seen[letter] {
				seen[letter] = true
				unassigned = append(unassigned, letter)
			}
		}

		for _, word := range p.addends {
			if column < len(word) {
				addLetter(word[len(word)-1-column], true)
			}
		}

		var resultLetter byte
		if column < len(p.result) {
			resultLetter = p.result[len(p.result)-1-column]
			addLetter(resultLetter, false)
		}

		sum := carry
		for letter, count := range addCounts {
			if digit, ok := assigned[letter]; ok {
				sum += digit * count
			}
		}

		var assign func(i, total int) bool
		assign = func(i, total int) bool {
			if i == len(unassigned) {
				target := 0
				if resultLetter != 0 {
					digit, ok := assigned[resultLetter]
					if !ok {
						return false
					}
					target = digit
				}
				if total%10 != target {
					return false
				}
				return search(column+1, total/10)
			}

			letter := unassigned[i]
			for digit := 0; digit <= 9; digit++ {
				if used[digit] {
					continue
				}
				if digit == 0 && p.leading[letter] {
					continue
				}
				used[digit] = true
				assigned[letter] = digit
				if assign(i+1, total+digit*addCounts[letter]) {
					return true
				}
				delete(assigned, letter)
				used[digit] = false
			}
			return false
		}

		return assign(0, sum)
	}

	if !search(0, 0) {
		return nil, errors.New("no solution")
	}

	answer := make(map[string]int, len(solution))
	for letter, digit := range solution {
		answer[string(letter)] = digit
	}
	return answer, nil
}
