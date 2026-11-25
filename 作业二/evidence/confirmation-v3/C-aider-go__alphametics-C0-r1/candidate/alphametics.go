package alphametics

import (
	"errors"
	"strings"
)

// Solve solves an alphametics puzzle such as "SEND + MORE == MONEY".
func Solve(puzzle string) (map[string]int, error) {
	parts := strings.Split(puzzle, "==")
	if len(parts) != 2 {
		return nil, errors.New("invalid puzzle: expected exactly one == operator")
	}

	var addends []string
	for _, w := range strings.Split(parts[0], "+") {
		w = strings.TrimSpace(w)
		if w == "" {
			return nil, errors.New("invalid puzzle: empty addend")
		}
		addends = append(addends, w)
	}
	result := strings.TrimSpace(parts[1])
	if result == "" {
		return nil, errors.New("invalid puzzle: empty result")
	}

	words := make([]string, 0, len(addends)+1)
	words = append(words, addends...)
	words = append(words, result)

	letters := make(map[byte]bool)
	for _, w := range words {
		for i := 0; i < len(w); i++ {
			c := w[i]
			if c < 'A' || c > 'Z' {
				return nil, errors.New("invalid puzzle: unexpected character")
			}
			letters[c] = true
		}
	}
	if len(letters) > 10 {
		return nil, errors.New("no solution: more than ten distinct letters")
	}

	// Digits of a multi-digit number may not be zero.
	leading := make(map[byte]bool)
	for _, w := range words {
		if len(w) > 1 {
			leading[w[0]] = true
		}
	}

	// A sum can never have fewer digits than its largest addend when no
	// leading zeros are allowed.
	for _, w := range addends {
		if len(w) > len(result) {
			return nil, errors.New("no solution")
		}
	}

	assign := make(map[byte]int, len(letters))
	var used [10]bool

	var dfs func(col, carry int) bool
	dfs = func(col, carry int) bool {
		if col == len(result) {
			return carry == 0
		}

		// Letters of this column that still need a digit, in a stable order.
		var un []byte
		seen := make(map[byte]bool, 4)
		for _, w := range addends {
			idx := len(w) - 1 - col
			if idx < 0 {
				continue
			}
			c := w[idx]
			if _, ok := assign[c]; ok {
				continue
			}
			if !seen[c] {
				seen[c] = true
				un = append(un, c)
			}
		}
		rl := result[len(result)-1-col]
		if _, ok := assign[rl]; !ok && !seen[rl] {
			seen[rl] = true
			un = append(un, rl)
		}

		var try func(i int) bool
		try = func(i int) bool {
			if i == len(un) {
				sum := carry
				for _, w := range addends {
					idx := len(w) - 1 - col
					if idx < 0 {
						continue
					}
					sum += assign[w[idx]]
				}
				if sum%10 != assign[rl] {
					return false
				}
				return dfs(col+1, sum/10)
			}
			c := un[i]
			for d := 0; d <= 9; d++ {
				if used[d] {
					continue
				}
				if d == 0 && leading[c] {
					continue
				}
				used[d] = true
				assign[c] = d
				if try(i + 1) {
					return true
				}
				delete(assign, c)
				used[d] = false
			}
			return false
		}
		return try(0)
	}

	if !dfs(0, 0) {
		return nil, errors.New("no solution")
	}

	out := make(map[string]int, len(assign))
	for c, d := range assign {
		out[string(c)] = d
	}
	return out, nil
}
