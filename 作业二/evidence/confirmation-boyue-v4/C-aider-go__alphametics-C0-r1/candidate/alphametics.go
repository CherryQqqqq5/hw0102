package alphametics

import (
	"errors"
	"strings"
)

// Solve attempts to solve the alphametics puzzle described by puzzle.
// It returns a mapping from each letter to its digit, or an error when
// the puzzle cannot be solved.
func Solve(puzzle string) (map[string]int, error) {
	// Remove every whitespace character so "SEND + MORE == MONEY" and
	// "SEND+MORE==MONEY" are handled identically.
	clean := strings.Join(strings.Fields(puzzle), "")

	sides := strings.Split(clean, "==")
	if len(sides) != 2 {
		return nil, errors.New("alphametics: puzzle must contain exactly one == operator")
	}

	left := strings.Split(sides[0], "+")
	addends := make([]string, 0, len(left))
	for _, word := range left {
		if word != "" {
			addends = append(addends, word)
		}
	}
	result := sides[1]

	if len(addends) == 0 || result == "" {
		return nil, errors.New("alphametics: puzzle must have at least one addend and a result")
	}

	for _, word := range addends {
		if !validWord(word) {
			return nil, errors.New("alphametics: invalid word in puzzle")
		}
	}
	if !validWord(result) {
		return nil, errors.New("alphametics: invalid result in puzzle")
	}

	// Every letter must map to a digit, therefore a puzzle with more than
	// ten distinct letters cannot have a solution.
	var letterPresent [26]bool
	for _, word := range addends {
		for i := 0; i < len(word); i++ {
			letterPresent[word[i]-'A'] = true
		}
	}
	for i := 0; i < len(result); i++ {
		letterPresent[result[i]-'A'] = true
	}

	letters := make([]byte, 0, 10)
	for i := 0; i < 26; i++ {
		if letterPresent[i] {
			letters = append(letters, byte('A'+i))
		}
	}
	if len(letters) > 10 {
		return nil, errors.New("alphametics: puzzle contains more than ten distinct letters")
	}

	// The leading digit of a multi-digit number must not be zero.
	// Single-letter numbers such as the "A" in "AS + A == MOM" may be zero.
	var leadingZeroForbidden [26]bool
	for _, word := range addends {
		if len(word) > 1 {
			leadingZeroForbidden[word[0]-'A'] = true
		}
	}
	if len(result) > 1 {
		leadingZeroForbidden[result[0]-'A'] = true
	}

	maxLen := len(result)
	for _, word := range addends {
		if len(word) > maxLen {
			maxLen = len(word)
		}
	}

	// A sum of non-negative numbers can never have fewer digits than its
	// largest addend.
	if len(result) < maxLen {
		return nil, errors.New("alphametics: no solution")
	}

	// colLetters[c] contains the distinct letters appearing in column c of
	// the addends (c == 0 is the units column).
	colLetters := make([][]byte, maxLen)
	resultLetter := make([]byte, maxLen)
	for c := 0; c < maxLen; c++ {
		var seen [26]bool
		for _, word := range addends {
			pos := len(word) - 1 - c
			if pos >= 0 {
				ch := word[pos]
				if !seen[ch-'A'] {
					seen[ch-'A'] = true
					colLetters[c] = append(colLetters[c], ch)
				}
			}
		}
		if c < len(result) {
			resultLetter[c] = result[len(result)-1-c]
		}
	}

	assign := make([]int, 26)
	for i := range assign {
		assign[i] = -1
	}
	var used [10]bool

	// search processes columns from right to left. carry is the value
	// carried into the current column.
	var search func(column, carry int) bool
	search = func(column, carry int) bool {
		// Assign every not-yet-assigned letter that occurs in this addend
		// column. The evaluation below then checks (and possibly derives)
		// the result digit.
		var unknown [10]byte
		n := 0
		for _, ch := range colLetters[column] {
			if assign[ch-'A'] == -1 {
				unknown[n] = ch
				n++
			}
		}

		var evaluate func() bool
		evaluate = func() bool {
			sum := carry
			for _, word := range addends {
				pos := len(word) - 1 - column
				if pos >= 0 {
					sum += assign[word[pos]-'A']
				}
			}

			want := sum % 10
			ch := resultLetter[column]
			idx := ch - 'A'

			wasNew := assign[idx] == -1
			if !wasNew {
				if assign[idx] != want {
					return false
				}
				carryOut := sum / 10
				if column == maxLen-1 {
					return carryOut == 0
				}
				return search(column+1, carryOut)
			}

			if used[want] || (want == 0 && leadingZeroForbidden[idx]) {
				return false
			}
			assign[idx] = want
			used[want] = true

			carryOut := sum / 10
			if column == maxLen-1 {
				if carryOut == 0 {
					// Successful solution: leave the derived digit in place.
					return true
				}
			} else if search(column+1, carryOut) {
				// A deeper column solved the puzzle, so keep this
				// derived digit assigned as well.
				return true
			}

			// This branch failed; undo the tentative result digit before
			// trying another combination in the enclosing search level.
			assign[idx] = -1
			used[want] = false
			return false
		}

		var assignUnknown func(int) bool
		assignUnknown = func(pos int) bool {
			if pos == n {
				return evaluate()
			}
			ch := unknown[pos]
			idx := ch - 'A'
			for digit := 0; digit <= 9; digit++ {
				if used[digit] || (digit == 0 && leadingZeroForbidden[idx]) {
					continue
				}
				used[digit] = true
				assign[idx] = digit
				if assignUnknown(pos + 1) {
					return true
				}
				assign[idx] = -1
				used[digit] = false
			}
			return false
		}

		return assignUnknown(0)
	}

	if !search(0, 0) {
		return nil, errors.New("alphametics: no solution")
	}

	solution := make(map[string]int, len(letters))
	for _, ch := range letters {
		solution[string(ch)] = assign[ch-'A']
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
