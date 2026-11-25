package alphametics

import (
	"errors"
	"strings"
)

// Solve solves an alphametics puzzle such as "SEND + MORE == MONEY" and
// returns the digit substitution for every letter. Each letter maps to a
// distinct digit and leading digits may not be zero.
func Solve(puzzle string) (map[string]int, error) {
	parts := strings.Split(puzzle, "==")
	if len(parts) != 2 {
		return nil, errors.New("invalid puzzle: expected exactly one ==")
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

	letters := map[byte]bool{}
	leading := map[byte]bool{}
	words := make([]string, 0, len(addends)+1)
	words = append(words, addends...)
	words = append(words, result)
	for _, w := range words {
		for i := 0; i < len(w); i++ {
			letters[w[i]] = true
		}
		if len(w) > 1 {
			leading[w[0]] = true
		}
	}
	if len(letters) > 10 {
		return nil, errors.New("invalid puzzle: more than ten distinct letters")
	}

	ncols := len(result)
	for _, w := range addends {
		if len(w) > ncols {
			ncols = len(w)
		}
	}

	// cols[c] holds the addend letters occupying column c (c = 0 is rightmost).
	cols := make([][]byte, ncols)
	for c := 0; c < ncols; c++ {
		for _, w := range addends {
			if c < len(w) {
				cols[c] = append(cols[c], w[len(w)-1-c])
			}
		}
	}
	// resCols[c] is the result letter for column c, or 0 if none.
	resCols := make([]byte, ncols)
	for c := 0; c < ncols; c++ {
		if c < len(result) {
			resCols[c] = result[len(result)-1-c]
		}
	}

	assign := map[byte]int{}
	var used [10]bool

	var solve func(c, carry int) bool
	solve = func(c, carry int) bool {
		if c == ncols {
			return carry == 0
		}

		var rec func(idx, sum int) bool
		rec = func(idx, sum int) bool {
			if idx == len(cols[c]) {
				total := sum + carry
				digit := total % 10
				nextCarry := total / 10
				rl := resCols[c]
				if rl == 0 {
					if digit != 0 {
						return false
					}
					return solve(c+1, nextCarry)
				}
				if d, ok := assign[rl]; ok {
					if d != digit {
						return false
					}
					return solve(c+1, nextCarry)
				}
				if used[digit] || (digit == 0 && leading[rl]) {
					return false
				}
				assign[rl] = digit
				used[digit] = true
				if solve(c+1, nextCarry) {
					return true
				}
				delete(assign, rl)
				used[digit] = false
				return false
			}

			l := cols[c][idx]
			if d, ok := assign[l]; ok {
				return rec(idx+1, sum+d)
			}
			for d := 0; d <= 9; d++ {
				if used[d] || (d == 0 && leading[l]) {
					continue
				}
				assign[l] = d
				used[d] = true
				if rec(idx+1, sum+d) {
					return true
				}
				delete(assign, l)
				used[d] = false
			}
			return false
		}
		return rec(0, 0)
	}

	if !solve(0, 0) {
		return nil, errors.New("no solution")
	}

	out := make(map[string]int, len(assign))
	for l, d := range assign {
		out[string(l)] = d
	}
	return out, nil
}
