package alphametics

import (
	"errors"
	"strings"
)

type column struct {
	counts [26]int
	result int // letter index of result digit in this column, or -1
}

// Solve returns a mapping from letters to digits that solves the alphametics
// puzzle, or an error if no solution exists.
func Solve(puzzle string) (map[string]int, error) {
	parts := strings.Split(puzzle, "==")
	if len(parts) != 2 {
		return nil, errors.New("invalid puzzle: expected exactly one ==")
	}

	parseSide := func(s string) ([]string, bool) {
		raw := strings.Split(s, "+")
		words := make([]string, 0, len(raw))
		for _, w := range raw {
			w = strings.Join(strings.Fields(w), "")
			if w == "" {
				return nil, false
			}
			words = append(words, w)
		}
		return words, true
	}

	addends, ok := parseSide(parts[0])
	if !ok {
		return nil, errors.New("invalid puzzle: empty addend")
	}
	resultWords, ok := parseSide(parts[1])
	if !ok || len(resultWords) != 1 {
		return nil, errors.New("invalid puzzle: expected exactly one result word")
	}
	result := resultWords[0]

	maxLen := len(result)
	for _, w := range addends {
		if len(w) > maxLen {
			maxLen = len(w)
		}
	}

	var leading [26]bool
	for _, w := range addends {
		for i := 0; i < len(w); i++ {
			c := w[i]
			if c < 'A' || c > 'Z' {
				return nil, errors.New("invalid puzzle: non-letter character")
			}
		}
		if len(w) > 1 {
			leading[w[0]-'A'] = true
		}
	}
	for i := 0; i < len(result); i++ {
		c := result[i]
		if c < 'A' || c > 'Z' {
			return nil, errors.New("invalid puzzle: non-letter character")
		}
	}
	if len(result) > 1 {
		leading[result[0]-'A'] = true
	}

	cols := make([]column, maxLen)
	for i := range cols {
		cols[i].result = -1
	}
	for _, w := range addends {
		for i := 0; i < len(w); i++ {
			letter := w[len(w)-1-i] - 'A'
			cols[i].counts[letter]++
		}
	}
	for i := 0; i < len(result); i++ {
		cols[i].result = int(result[len(result)-1-i] - 'A')
	}

	var assign [26]int
	for i := range assign {
		assign[i] = -1
	}
	var used [10]bool

	var dfs func(col, carry int) bool
	dfs = func(col, carry int) bool {
		if col == maxLen {
			return carry == 0
		}

		c := &cols[col]
		var unknown []int
		sum := carry
		for l := 0; l < 26; l++ {
			if c.counts[l] == 0 {
				continue
			}
			if assign[l] >= 0 {
				sum += c.counts[l] * assign[l]
			} else {
				unknown = append(unknown, l)
			}
		}

		var try func(k int) bool
		try = func(k int) bool {
			if k == len(unknown) {
				digit := sum % 10
				nextCarry := sum / 10
				r := c.result
				if r < 0 {
					// Extra column beyond the result: nothing may carry out.
					if digit != 0 {
						return false
					}
					return dfs(col+1, nextCarry)
				}
				if assign[r] >= 0 {
					if assign[r] != digit {
						return false
					}
					return dfs(col+1, nextCarry)
				}
				if used[digit] || (leading[r] && digit == 0) {
					return false
				}
				assign[r] = digit
				used[digit] = true
				if dfs(col+1, nextCarry) {
					return true
				}
				assign[r] = -1
				used[digit] = false
				return false
			}

			l := unknown[k]
			for d := 0; d <= 9; d++ {
				if used[d] || (leading[l] && d == 0) {
					continue
				}
				assign[l] = d
				used[d] = true
				sum += c.counts[l] * d
				if try(k + 1) {
					return true
				}
				sum -= c.counts[l] * d
				assign[l] = -1
				used[d] = false
			}
			return false
		}

		return try(0)
	}

	if !dfs(0, 0) {
		return nil, errors.New("no solution")
	}

	solution := make(map[string]int)
	for l := 0; l < 26; l++ {
		if assign[l] >= 0 {
			solution[string(rune('A'+l))] = assign[l]
		}
	}
	return solution, nil
}
