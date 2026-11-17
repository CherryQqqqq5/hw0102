package alphametics

import (
	"errors"
	"sort"
	"strings"
)

var errNoSolution = errors.New("no solution")

type columnTerm struct {
	idx   int
	count int
}

func Solve(puzzle string) (map[string]int, error) {
	addends, result, words, ok := parsePuzzle(puzzle)
	if !ok {
		return nil, errNoSolution
	}

	letterIndex := make(map[byte]int)
	letters := make([]byte, 0, 10)
	for _, word := range words {
		for i := 0; i < len(word); i++ {
			c := word[i]
			if _, exists := letterIndex[c]; !exists {
				letterIndex[c] = len(letters)
				letters = append(letters, c)
			}
		}
	}
	if len(letters) > 10 {
		return nil, errNoSolution
	}

	var leadMask uint16
	for _, word := range words {
		if len(word) > 1 {
			leadMask |= 1 << uint(letterIndex[word[0]])
		}
	}

	maxLen := 0
	for _, word := range words {
		if len(word) > maxLen {
			maxLen = len(word)
		}
	}

	colTerms := make([][]columnTerm, maxLen)
	for col := 0; col < maxLen; col++ {
		counts := make(map[int]int)
		for _, addend := range addends {
			if col < len(addend) {
				idx := letterIndex[addend[len(addend)-1-col]]
				counts[idx]++
			}
		}
		terms := make([]columnTerm, 0, len(counts))
		for idx, count := range counts {
			terms = append(terms, columnTerm{idx: idx, count: count})
		}
		sort.Slice(terms, func(i, j int) bool {
			if terms[i].count != terms[j].count {
				return terms[i].count > terms[j].count
			}
			return terms[i].idx < terms[j].idx
		})
		colTerms[col] = terms
	}

	colResult := make([]int, maxLen)
	for i := range colResult {
		colResult[i] = -1
	}
	for col := 0; col < len(result); col++ {
		colResult[col] = letterIndex[result[len(result)-1-col]]
	}

	var values [10]int
	var used uint16
	var usedDigits uint16

	var dfs func(col, carry int) bool
	dfs = func(col, carry int) bool {
		if col == maxLen {
			return carry == 0
		}

		terms := colTerms[col]
		resultIdx := colResult[col]

		var assignAddends func(pos, sum int) bool
		assignAddends = func(pos, sum int) bool {
			for pos < len(terms) {
				term := terms[pos]
				bit := uint16(1 << uint(term.idx))
				if used&bit != 0 {
					sum += term.count * values[term.idx]
					pos++
					continue
				}
				for digit := 0; digit < 10; digit++ {
					if digit == 0 && leadMask&bit != 0 {
						continue
					}
					digitBit := uint16(1 << uint(digit))
					if usedDigits&digitBit != 0 {
						continue
					}
					values[term.idx] = digit
					used |= bit
					usedDigits |= digitBit
					if assignAddends(pos+1, sum+term.count*digit) {
						return true
					}
					used &^= bit
					usedDigits &^= digitBit
					values[term.idx] = 0
				}
				return false
			}

			total := sum + carry
			if resultIdx < 0 {
				if total%10 != 0 {
					return false
				}
				return dfs(col+1, total/10)
			}

			resultBit := uint16(1 << uint(resultIdx))
			if used&resultBit != 0 {
				if total%10 != values[resultIdx] {
					return false
				}
				return dfs(col+1, total/10)
			}

			resultDigit := total % 10
			if resultDigit == 0 && leadMask&resultBit != 0 {
				return false
			}
			resultDigitBit := uint16(1 << uint(resultDigit))
			if usedDigits&resultDigitBit != 0 {
				return false
			}
			values[resultIdx] = resultDigit
			used |= resultBit
			usedDigits |= resultDigitBit
			if dfs(col+1, total/10) {
				return true
			}
			used &^= resultBit
			usedDigits &^= resultDigitBit
			values[resultIdx] = 0
			return false
		}

		return assignAddends(0, 0)
	}

	if !dfs(0, 0) {
		return nil, errNoSolution
	}

	solution := make(map[string]int, len(letters))
	for idx, letter := range letters {
		solution[string(letter)] = values[idx]
	}
	return solution, nil
}

func parsePuzzle(puzzle string) ([]string, string, []string, bool) {
	parts := strings.Split(puzzle, "==")
	if len(parts) != 2 {
		return nil, "", nil, false
	}

	left := strings.TrimSpace(parts[0])
	right := strings.TrimSpace(parts[1])
	if left == "" || right == "" {
		return nil, "", nil, false
	}

	rawAddends := strings.Split(left, "+")
	addends := make([]string, 0, len(rawAddends))
	for _, addend := range rawAddends {
		addend = strings.TrimSpace(addend)
		if !validWord(addend) {
			return nil, "", nil, false
		}
		addends = append(addends, addend)
	}
	if !validWord(right) {
		return nil, "", nil, false
	}

	words := make([]string, 0, len(addends)+1)
	words = append(words, addends...)
	words = append(words, right)
	return addends, right, words, true
}

func validWord(word string) bool {
	if word == "" {
		return false
	}
	for i := 0; i < len(word); i++ {
		c := word[i]
		if c < 'A' || c > 'Z' {
			return false
		}
	}
	return true
}
