package alphametics

import (
	"fmt"
	"sort"
	"strings"
)

// Solve attempts to solve an alphametics puzzle.
func Solve(puzzle string) (map[string]int, error) {
	parts := strings.Split(puzzle, "==")
	if len(parts) != 2 {
		return nil, fmt.Errorf("puzzle must contain exactly one == operator")
	}

	left := strings.TrimSpace(parts[0])
	right := strings.TrimSpace(parts[1])
	if left == "" || right == "" {
		return nil, fmt.Errorf("puzzle has an empty side")
	}

	addends := make([]string, 0)
	for _, word := range strings.Split(left, "+") {
		word = strings.TrimSpace(word)
		if word == "" {
			return nil, fmt.Errorf("puzzle has an empty addend")
		}
		if err := validateWord(word); err != nil {
			return nil, err
		}
		addends = append(addends, word)
	}
	if err := validateWord(right); err != nil {
		return nil, err
	}
	if len(addends) == 0 {
		return nil, fmt.Errorf("puzzle has no addends")
	}

	maxLen := len(right)
	for _, word := range addends {
		if len(word) > maxLen {
			maxLen = len(word)
		}
	}

	var digit [26]int
	for i := range digit {
		digit[i] = -1
	}
	var used [10]bool
	var leading [26]bool
	for _, word := range addends {
		if len(word) > 1 {
			leading[word[0]-'A'] = true
		}
	}
	if len(right) > 1 {
		leading[right[0]-'A'] = true
	}

	var solved bool
	var dfsColumn func(col, carry int) bool

	dfsColumn = func(col, carry int) bool {
		if col == maxLen {
			return carry == 0
		}

		var coeff [26]int
		unknown := make([]int, 0, 10)

		for _, word := range addends {
			if col < len(word) {
				idx := int(word[len(word)-1-col] - 'A')
				if coeff[idx] == 0 && digit[idx] == -1 {
					unknown = append(unknown, idx)
				}
				coeff[idx]++
			}
		}

		resultIdx := -1
		if col < len(right) {
			resultIdx = int(right[len(right)-1-col] - 'A')
			if coeff[resultIdx] == 0 && digit[resultIdx] == -1 {
				unknown = append(unknown, resultIdx)
			}
		}

		// Assign high-impact letters first to prune earlier.
		sort.Slice(unknown, func(i, j int) bool {
			return coeff[unknown[i]] > coeff[unknown[j]]
		})

		// Include contributions of letters already assigned in earlier columns.
		baseSum := carry
		for idx := 0; idx < 26; idx++ {
			if coeff[idx] > 0 && digit[idx] != -1 {
				baseSum += coeff[idx] * digit[idx]
			}
		}

		var assign func(pos, sum int) bool
		assign = func(pos, sum int) bool {
			if pos == len(unknown) {
				if resultIdx >= 0 {
					if digit[resultIdx] == -1 || sum%10 != digit[resultIdx] {
						return false
					}
					return dfsColumn(col+1, sum/10)
				}
				// A sum may not extend beyond the result word.
				if sum != 0 {
					return false
				}
				return dfsColumn(col+1, 0)
			}

			if resultIdx < 0 && sum > 0 {
				return false
			}

			idx := unknown[pos]
			c := coeff[idx]
			for d := 0; d <= 9; d++ {
				if used[d] || (d == 0 && leading[idx]) {
					continue
				}
				used[d] = true
				digit[idx] = d
				if assign(pos+1, sum+c*d) {
					return true
				}
				digit[idx] = -1
				used[d] = false
			}
			return false
		}

		if assign(0, baseSum) {
			solved = true
			return true
		}
		return false
	}

	if !dfsColumn(0, 0) || !solved {
		return nil, fmt.Errorf("no solution")
	}

	solution := make(map[string]int)
	for i, d := range digit {
		if d >= 0 {
			solution[string(rune('A'+i))] = d
		}
	}
	return solution, nil
}

func validateWord(word string) error {
	for i := 0; i < len(word); i++ {
		if word[i] < 'A' || word[i] > 'Z' {
			return fmt.Errorf("invalid character %q in word %q", word[i], word)
		}
	}
	return nil
}
