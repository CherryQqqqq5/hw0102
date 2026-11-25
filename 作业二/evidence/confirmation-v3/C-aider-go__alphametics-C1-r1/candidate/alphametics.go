package alphametics

import (
	"errors"
	"sort"
	"strings"
)

type column struct {
	add [26]int
	res int
}

var (
	assign  [26]int
	used    [10]bool
	leading [26]bool
	cols    []column
)

// Solve solves an alphametics puzzle.  Every letter is replaced by a distinct
// digit, and the leading digit of a multi-digit number may not be zero.
func Solve(puzzle string) (map[string]int, error) {
	cleaned := strings.Map(func(r rune) rune {
		if r == ' ' || r == '\t' || r == '\n' || r == '\r' {
			return -1
		}
		return r
	}, puzzle)

	parts := strings.Split(cleaned, "==")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return nil, errors.New("invalid puzzle")
	}

	addends := strings.Split(parts[0], "+")
	result := parts[1]

	for _, w := range addends {
		if w == "" {
			return nil, errors.New("invalid puzzle")
		}
	}
	if result == "" {
		return nil, errors.New("invalid puzzle")
	}

	// Validate input and reset the package-level search state.
	for i := 0; i < 26; i++ {
		assign[i] = -1
		leading[i] = false
	}
	for i := 0; i < 10; i++ {
		used[i] = false
	}

	validWord := func(w string) bool {
		for i := 0; i < len(w); i++ {
			if w[i] < 'A' || w[i] > 'Z' {
				return false
			}
		}
		return true
	}

	maxLen := len(result)
	for _, w := range append(addends, result) {
		if !validWord(w) {
			return nil, errors.New("invalid puzzle")
		}
		if len(w) > maxLen {
			maxLen = len(w)
		}
		if len(w) > 1 {
			leading[w[0]-'A'] = true
		}
	}

	cols = make([]column, maxLen)
	for i := range cols {
		cols[i].res = -1
	}

	for _, w := range addends {
		for i := 0; i < len(w); i++ {
			cols[i].add[w[len(w)-1-i]-'A']++
		}
	}
	for i := 0; i < len(result); i++ {
		cols[i].res = int(result[len(result)-1-i] - 'A')
	}

	if !search(0, 0) {
		return nil, errors.New("no solution")
	}

	letters := make(map[string]int)
	for i := 0; i < 26; i++ {
		if assign[i] >= 0 {
			letters[string(rune('A'+i))] = assign[i]
		}
	}
	return letters, nil
}

func search(col, carry int) bool {
	if col == len(cols) {
		return carry == 0
	}

	c := &cols[col]
	unknown := make([]int, 0, 10)
	base := carry
	for l := 0; l < 26; l++ {
		if c.add[l] > 0 {
			if assign[l] >= 0 {
				base += c.add[l] * assign[l]
			} else {
				unknown = append(unknown, l)
			}
		}
	}
	// Trying the most frequent letters first tends to prune much earlier.
	sort.Slice(unknown, func(i, j int) bool {
		return c.add[unknown[i]] > c.add[unknown[j]]
	})

	return assignAddends(col, c, unknown, 0, base)
}

func assignAddends(col int, c *column, unknown []int, idx, sum int) bool {
	if idx == len(unknown) {
		total := sum
		digit := total % 10
		nextCarry := total / 10

		if c.res < 0 {
			// There is no result digit in this column, so no non-zero digit
			// may be produced here.
			if digit != 0 {
				return false
			}
			return search(col+1, nextCarry)
		}

		r := c.res
		if assign[r] >= 0 {
			if assign[r] != digit {
				return false
			}
			return search(col+1, nextCarry)
		}
		if used[digit] || (digit == 0 && leading[r]) {
			return false
		}

		assign[r] = digit
		used[digit] = true
		if search(col+1, nextCarry) {
			return true
		}
		assign[r] = -1
		used[digit] = false
		return false
	}

	l := unknown[idx]
	for d := 0; d <= 9; d++ {
		if used[d] || (d == 0 && leading[l]) {
			continue
		}
		assign[l] = d
		used[d] = true
		if assignAddends(col, c, unknown, idx+1, sum+c.add[l]*d) {
			return true
		}
		assign[l] = -1
		used[d] = false
	}
	return false
}
