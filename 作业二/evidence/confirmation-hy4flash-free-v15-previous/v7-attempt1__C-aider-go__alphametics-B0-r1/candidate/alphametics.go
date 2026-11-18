package alphametics

import (
	"errors"
	"sort"
	"strings"
)

var errNoSolution = errors.New("no solution")

type solver struct {
	addendCount int
	n           int
	letterCount int
	coeff       [][]int
	involved    [][]int
	leading     []bool
	values      []int
}

func Solve(puzzle string) (map[string]int, error) {
	parts := strings.Split(puzzle, "==")
	if
