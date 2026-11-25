package alphametics

import (
	"errors"
	"strings"
)

func Solve(puzzle string) (map[string]int, error) {
	compact := strings.Join(strings.Fields(puzzle), "")
	parts := strings.Split(compact, "==")
	if len(parts) != 2 {
		return nil, errors.New("invalid puzzle: expected exactly one ==")
	}

	left, result := parts[0], parts[1]
	if left == "" || result == "" {
		return nil, errors.New("invalid puzzle: missing addend or result")
	}

	addends := strings.Split(left, "+")
	for _, w := range addends {
		if w == "" {
			return nil, errors.New("invalid puzzle: empty addend")
		}
		if len(w) > len(result) {
			return nil, errors.New("no solution: addend is longer than result")
		}
	}

	letterID := make(map[byte]int)
	var letters []byte
	addLetters := func(w string) {
		for i := 0; i < len(w); i++ {
			ch := w[i]
			if _, ok := letterID[ch]; !ok {
				letterID[ch] = len(letters)
				letters = append(letters, ch)
			}
		}
	}
	for _, w := range addends {
		addLetters(w)
	}
	addLetters(result)

	n := len(letters)
	if n > 10 {
		return nil, errors.New("no solution: more than ten distinct letters")
	}

	// A leading digit of a multi-digit number cannot be zero.
	leading := make([]bool, n)
	for _, w := range addends {
		if len(w) > 1 {
			leading[letterID[w[0]]] = true
		}
	}
	if len(result) > 1 {
		leading[letterID[result[0]]] = true
	}

	// counts[column][letter] is how many times letter occurs in that column
	// among the addends, counting from the right.
	cols := len(result)
	counts := make([][]int, cols)
	for col := 0; col < cols; col++ {
		counts[col] = make([]int, n)
	}
	for _, w := range addends {
		for pos := 0; pos < len(w); pos++ {
			ch := w[len(w)-1-pos]
			counts[pos][letterID[ch]]++
		}
	}

	resultLetter := make([]int, cols)
	for pos := 0; pos < cols; pos++ {
		resultLetter[pos] = letterID[result[len(result)-1-pos]]
	}

	assigned := make([]int, n)
	for i := range assigned {
		assigned[i] = -1
	}
	var used [10]bool

	var dfs func(col, carry int) bool
	dfs = func(col, carry int) bool {
		if col == cols {
			if carry != 0 {
				return false
			}
			for _, d := range assigned {
				if d < 0 {
					return false
				}
			}
			return true
		}

		unknown := make([]int, 0, n)
		seen := make([]bool, n)
		for i := 0; i < n; i++ {
			if counts[col][i] > 0 && assigned[i] < 0 {
				unknown = append(unknown, i)
				seen[i] = true
			}
		}
		ri := resultLetter[col]
		if assigned[ri] < 0 && !seen[ri] {
			unknown = append(unknown, ri)
		}

		var assign func(k int) bool
		assign = func(k int) bool {
			if k == len(unknown) {
				sum := carry
				for i := 0; i < n; i++ {
					if counts[col][i] != 0 {
						sum += counts[col][i] * assigned[i]
					}
				}
				if sum%10 != assigned[ri] {
					return false
				}
				return dfs(col+1, sum/10)
			}

			idx := unknown[k]
			for d := 0; d <= 9; d++ {
				if used[d] {
					continue
				}
				if d == 0 && leading[idx] {
					continue
				}
				used[d] = true
				assigned[idx] = d
				if assign(k + 1) {
					return true
				}
				assigned[idx] = -1
				used[d] = false
			}
			return false
		}

		return assign(0)
	}

	if !dfs(0, 0) {
		return nil, errors.New("no solution")
	}

	solution := make(map[string]int, n)
	for i, ch := range letters {
		solution[string(ch)] = assigned[i]
	}
	return solution, nil
}
