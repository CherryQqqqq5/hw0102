package alphametics

import (
	"errors"
	"strings"
)

type addendTerm struct {
	letter byte
	count  int
}

// Solve returns the digit substitution that makes the alphametics puzzle valid.
func Solve(puzzle string) (map[string]int, error) {
	parts := strings.Split(puzzle, "==")
	if len(parts) != 2 {
		return nil, errors.New("puzzle must contain exactly one ==")
	}

	addendPart := strings.TrimSpace(parts[0])
	resultWord := strings.TrimSpace(parts[1])
	if addendPart == "" || resultWord == "" {
		return nil, errors.New("puzzle has an empty side")
	}

	addends := strings.Split(addendPart, "+")
	for i := range addends {
		addends[i] = strings.TrimSpace(addends[i])
		if addends[i] == "" {
			return nil, errors.New("puzzle has an empty addend")
		}
	}

	numColumns := len(resultWord)
	for _, word := range addends {
		if len(word) > numColumns {
			return nil, errors.New("result is shorter than an addend")
		}
	}

	leading := make(map[byte]bool)
	for _, word := range append(addends, resultWord) {
		if len(word) > 1 {
			leading[word[0]] = true
		}
	}

	// Sum the addend letters in each decimal column, from right to left.
	addendColumns := make([][]addendTerm, numColumns)
	for column := 0; column < numColumns; column++ {
		counts := make(map[byte]int)
		for _, word := range addends {
			index := len(word) - 1 - column
			if index >= 0 {
				counts[word[index]]++
			}
		}
		for letter, count := range counts {
			addendColumns[column] = append(addendColumns[column], addendTerm{letter, count})
		}
	}

	resultLetters := make([]byte, numColumns)
	for column := 0; column < numColumns; column++ {
		resultLetters[column] = resultWord[len(resultWord)-1-column]
	}

	assignment := make(map[byte]int)
	used := [10]bool{}

	var search func(column, carry int) bool
	search = func(column, carry int) bool {
		if column == numColumns {
			return carry == 0
		}

		var unassigned []byte
		seen := make(map[byte]bool)
		for _, term := range addendColumns[column] {
			if _, ok := assignment[term.letter]; !ok && !seen[term.letter] {
				seen[term.letter] = true
				unassigned = append(unassigned, term.letter)
			}
		}
		resultLetter := resultLetters[column]
		if _, ok := assignment[resultLetter]; !ok && !seen[resultLetter] {
			seen[resultLetter] = true
			unassigned = append(unassigned, resultLetter)
		}

		columnTotal := func() int {
			total := carry
			for _, term := range addendColumns[column] {
				total += term.count * assignment[term.letter]
			}
			return total - assignment[resultLetter]
		}

		if len(unassigned) == 0 {
			total := columnTotal()
			if total < 0 || total%10 != 0 {
				return false
			}
			return search(column+1, total/10)
		}

		var assign func(int) bool
		assign = func(index int) bool {
			if index == len(unassigned) {
				total := columnTotal()
				if total < 0 || total%10 != 0 {
					return false
				}
				return search(column+1, total/10)
			}

			letter := unassigned[index]
			start := 0
			if leading[letter] {
				start = 1
			}
			for digit := start; digit < 10; digit++ {
				if used[digit] {
					continue
				}
				assignment[letter] = digit
				used[digit] = true
				if assign(index + 1) {
					return true
				}
				delete(assignment, letter)
				used[digit] = false
			}
			return false
		}

		return assign(0)
	}

	if !search(0, 0) {
		return nil, errors.New("puzzle has no solution")
	}
	solution := make(map[string]int, len(assignment))
	for letter, digit := range assignment {
		solution[string(letter)] = digit
	}
	return solution, nil
}
