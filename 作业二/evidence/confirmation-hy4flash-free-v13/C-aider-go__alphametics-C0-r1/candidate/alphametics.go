package alphametics

import (
	"errors"
	"strings"
)

type column struct {
	counts []int
	target int
}

type solver struct {
	letters     []string
	index       map[string]int
	leading     []bool
	columns     []column
	addendCount int
	assignment  []int
}

func Solve(puzzle string) (map[string]int, error) {
	s, err := newSolver(puzzle)
	if err != nil {
		return nil, err
	}
	if !s.search(0, 0) {
		return nil, errors.New("no solution")
	}
	result := make(map[string]int, len(s.letters))
	for i, letter := range s.letters {
		result[letter] = s.assignment[i]
	}
	return result, nil
}

func newSolver(puzzle string) (*solver, error) {
	parts := strings.Split(puzzle, "==")
	if len(parts) != 2 {
		return nil, errors.New("invalid puzzle")
	}
	resultText := strings.TrimSpace(parts[1])
	if resultText == "" {
		return nil, errors.New("invalid puzzle")
	}

	s := &solver{index: make(map[string]int)}

	addends := make([][]int, 0, len(strings.Split(parts[0], "+")))
	for _, text := range strings.Split(parts[0], "+") {
		word, err := s.parseWord(text)
		if err != nil {
			return nil, err
		}
		addends = append(addends, word)
	}
	resultWord, err := s.parseWord(resultText)
	if err != nil {
		return nil, err
	}
	if len(s.letters) > 10 {
		return nil, errors.New("too many letters")
	}

	maxAddendLen := 0
	for _, word := range addends {
		if len(word) > maxAddendLen {
			maxAddendLen = len(word)
		}
	}
	if len(resultWord) < maxAddendLen {
		return nil, errors.New("no solution")
	}

	s.assignment = make([]int, len(s.letters))
	for i := range s.assignment {
		s.assignment[i] = -1
	}
	s.addendCount = len(addends)
	s.columns = make([]column, len(resultWord))
	for col := range s.columns {
		counts := make([]int, len(s.letters))
		for _, word := range addends {
			if pos := len(word) - 1 - col; pos >= 0 {
				counts[word[pos]]++
			}
		}
		target := -1
		if col < len(resultWord) {
			target = resultWord[len(resultWord)-1-col]
		}
		s.columns[col] = column{counts: counts, target: target}
	}
	return s, nil
}

func (s *solver) parseWord(text string) ([]int, error) {
	text = strings.TrimSpace(text)
	if text == "" {
		return nil, errors.New("invalid puzzle")
	}
	word := make([]int, 0, len(text))
	for i := 0; i < len(text); i++ {
		ch := text[i]
		if ch < 'A' || ch > 'Z' {
			return nil, errors.New("invalid puzzle")
		}
		key := string(ch)
		idx, ok := s.index[key]
		if !ok {
			idx = len(s.letters)
			s.index[key] = idx
			s.letters = append(s.letters, key)
			s.leading = append(s.leading, false)
		}
		word = append(word, idx)
	}
	if len(word) > 1 {
		s.leading[word[0]] = true
	}
	return word, nil
}

func (s *solver) search(col, carry int) bool {
	if col == len(s.columns) {
		return carry == 0
	}
	c := s.columns[col]
	vars := make([]int, 0, len(s.letters))
	for i, count := range c.counts {
		if count > 0 && s.assignment[i] < 0 {
			vars = append(vars, i)
		}
	}
	if c.target >= 0 && s.assignment[c.target] < 0 && c.counts[c.target] == 0 {
		vars = append(vars, c.target)
	}
	return s.assignColumn(vars, 0, col, carry)
}

func (s *solver) assignColumn(vars []int, pos, col, carry int) bool {
	if pos == len(vars) {
		return s.checkColumn(col, carry)
	}
	v := vars[pos]
	for digit := 9; digit >= 0; digit-- {
		if s.used(digit) || (s.leading[v] && digit == 0) {
			continue
		}
		s.assignment[v] = digit
		if s.assignColumn(vars, pos+1, col, carry) {
			return true
		}
		s.assignment[v] = -1
	}
	return false
}

func (s *solver) used(digit int) bool {
	for _, assigned := range s.assignment {
		if assigned == digit {
			return true
		}
	}
	return false
}

func (s *solver) checkColumn(col, carry int) bool {
	c := s.columns[col]
	sum := carry
	for i, count := range c.counts {
		if count > 0 {
			sum += count * s.assignment[i]
		}
	}
	if c.target < 0 {
		if sum%10 != 0 {
			return false
		}
		return s.search(col+1, sum/10)
	}
	if sum%10 != s.assignment[c.target] {
		return false
	}
	nextCarry := sum / 10
	if nextCarry > s.addendCount {
		return false
	}
	return s.search(col+1, nextCarry)
}
