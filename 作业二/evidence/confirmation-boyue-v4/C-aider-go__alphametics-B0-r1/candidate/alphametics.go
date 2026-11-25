package alphametics

import (
	"errors"
	"strings"
)

// Solve attempts to find digit assignments for every letter in puzzle such that
// the stated addition equation is true. Each letter maps to a different digit,
// and the leading letter of a multi-letter word may not be zero.
func Solve(puzzle string) (map[string]int, error) {
	// Normalize the operators so the puzzle can be parsed by strings.Fields.
	normalized := strings.ReplaceAll(puzzle, "==", " == ")
	normalized = strings.ReplaceAll(normalized, "+", " + ")
	fields := strings.Fields(normalized)
	if len(fields) == 0 {
		return nil, errors.New("empty puzzle")
	}

	// Split the tokens at the equality operator.
	var addendTokens, resultTokens []string
	afterEquals := false
	for _, token := range fields {
		switch token {
		case "==":
			if afterEquals {
				return nil, errors.New("multiple equality operators")
			}
			afterEquals = true
		case "+":
			// Operators are validated by the term collection below.
		default:
			if !allLetters(token) {
				return nil, errors.New("invalid word")
			}
			if afterEquals {
				resultTokens = append(resultTokens, token)
			} else {
				addendTokens = append(addendTokens, token)
			}
		}
	}

	if !afterEquals || len(addendTokens) == 0 || len(resultTokens) != 1 {
		return nil, errors.New("malformed puzzle")
	}

	// Validate the term/operator pattern.
	wantTerm := true
	onRight := false
	for _, token := range fields {
		switch token {
		case "==":
			if wantTerm || onRight {
				return nil, errors.New("malformed puzzle")
			}
			wantTerm = true
			onRight = true
		case "+":
			if wantTerm || onRight {
				return nil, errors.New("malformed puzzle")
			}
			wantTerm = true
		default:
			if !wantTerm {
				return nil, errors.New("malformed puzzle")
			}
			wantTerm = false
		}
	}
	if wantTerm {
		return nil, errors.New("malformed puzzle")
	}

	addends := make([][]byte, 0, len(addendTokens))
	for _, term := range addendTokens {
		addends = append(addends, []byte(term))
	}
	result := []byte(resultTokens[0])

	distinct := make(map[byte]bool)
	for _, term := range addends {
		for i := 0; i < len(term); i++ {
			distinct[term[i]] = true
		}
	}
	for i := 0; i < len(result); i++ {
		distinct[result[i]] = true
	}
	if len(distinct) > 10 {
		return nil, errors.New("more than ten distinct letters")
	}

	maxLen := len(result)
	for _, term := range addends {
		if len(term) > maxLen {
			maxLen = len(term)
		}
	}

	// The first letter of any multi-letter word cannot be zero.
	var leading [26]bool
	for _, term := range addends {
		if len(term) > 1 {
			leading[term[0]-'A'] = true
		}
	}
	if len(result) > 1 {
		leading[result[0]-'A'] = true
	}

	var used [10]bool
	var assigned [26]bool
	var digits [26]int

	var answer map[string]int

	buildAnswer := func() map[string]int {
		m := make(map[string]int, len(distinct))
		for i, ok := range assigned {
			if ok {
				m[string(rune('A'+i))] = digits[i]
			}
		}
		return m
	}

	var assignUnknowns func(col, carry int, unknown []byte, index int) bool
	var searchColumn func(col, carry int) bool

	searchColumn = func(col, carry int) bool {
		if col == maxLen {
			if carry != 0 {
				return false
			}
			answer = buildAnswer()
			return true
		}

		// Collect the distinct, not-yet-assigned letters involved in this column.
		var unknown []byte
		seenHere := make(map[byte]bool)
		addIfNeeded := func(letter byte) {
			idx := letter - 'A'
			if assigned[idx] || seenHere[idx] {
				return
			}
			seenHere[idx] = true
			unknown = append(unknown, letter)
		}
		for _, term := range addends {
			if len(term) > col {
				addIfNeeded(term[len(term)-1-col])
			}
		}
		if len(result) > col {
			addIfNeeded(result[len(result)-1-col])
		}

		return assignUnknowns(col, carry, unknown, 0)
	}

	assignUnknowns = func(col, carry int, unknown []byte, index int) bool {
		if index == len(unknown) {
			total := carry
			for _, term := range addends {
				if len(term) > col {
					total += digits[term[len(term)-1-col]-'A']
				}
			}
			if len(result) > col {
				total -= digits[result[len(result)-1-col]-'A']
			}

			if total < 0 || total%10 != 0 {
				return false
			}
			return searchColumn(col+1, total/10)
		}

		letterIdx := unknown[index] - 'A'
		for digit := 0; digit <= 9; digit++ {
			if used[digit] {
				continue
			}
			if digit == 0 && leading[letterIdx] {
				continue
			}

			used[digit] = true
			assigned[letterIdx] = true
			digits[letterIdx] = digit

			if assignUnknowns(col, carry, unknown, index+1) {
				return true
			}

			used[digit] = false
			assigned[letterIdx] = false
		}
		return false
	}

	if !searchColumn(0, 0) {
		return nil, errors.New("no solution")
	}
	return answer, nil
}

func allLetters(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < 'A' || s[i] > 'Z' {
			return false
		}
	}
	return true
}
