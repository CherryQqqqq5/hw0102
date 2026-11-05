package connect

import (
	"fmt"
	"strings"
)

var neighborOffsets = [][2]int{
	{-1, 0},
	{-1, 1},
	{0, -1},
	{0, 1},
	{1, -1},
	{1, 0},
}

func ResultOf(lines []string) (string, error) {
	if len(lines) == 0 {
		return "", nil
	}

	board := make([]string, len(lines))
	width := -1
	for r, line := range lines {
		line = strings.ReplaceAll(line, " ", "")
		if width == -1 {
			width = len(line)
		} else if len(line) != width {
			return "", fmt.Errorf("connect: row %d has length %d, want %d", r, len(line), width)
		}
		board[r] = line
	}

	if width == 0 {
		return "", nil
	}

	if connects(board, 'O',
		func(r, _ int) bool { return r == 0 },
		func(r, _ int) bool { return r == len(board)-1 },
	) {
		return "O", nil
	}

	if connects(board, 'X',
		func(_, c int) bool { return c == 0 },
		func(_, c int) bool { return c == width-1 },
	) {
		return "X", nil
	}

	return "", nil
}

func connects(board []string, player byte, starts, ends func(r, c int) bool) bool {
	rows, cols := len(board), len(board[0])
	visited := make([][]bool, rows)
	for r := range visited {
		visited[r] = make([]bool, cols)
	}

	type cell struct{ row, col int }
	queue := make([]cell, 0, rows*cols)

	for r := 0; r < rows; r++ {
		for c := 0; c < cols; c++ {
			if board[r][c] != player || !starts(r, c) {
				continue
			}
			if ends(r, c) {
				return true
			}
			visited[r][c] = true
			queue = append(queue, cell{r, c})
		}
	}

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		for _, offset := range neighborOffsets {
			r := current.row + offset[0]
			c := current.col + offset[1]
			if r < 0 || r >= rows || c < 0 || c >= cols {
				continue
			}
			if visited[r][c] || board[r][c] != player {
				continue
			}
			if ends(r, c) {
				return true
			}
			visited[r][c] = true
			queue = append(queue, cell{r, c})
		}
	}

	return false
}
