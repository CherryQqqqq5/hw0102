package connect

import (
	"fmt"
	"strings"
)

type cell struct {
	row, col int
}

func ResultOf(lines []string) (string, error) {
	board := make([]string, len(lines))
	for i, line := range lines {
		board[i] = strings.ReplaceAll(line, " ", "")
	}

	if len(board) == 0 {
		return "", nil
	}

	height := len(board)
	width := len(board[0])
	if width == 0 {
		return "", nil
	}

	for i, line := range board {
		if len(line) != width {
			return "", fmt.Errorf("invalid board: row %d has width %d, want %d", i, len(line), width)
		}
	}

	// X wins by connecting the left side to the right side.
	if connected(board, 'X',
		func(_, col int) bool { return col == 0 },
		func(_, col int) bool { return col == width-1 },
	) {
		return "X", nil
	}

	// O wins by connecting the top side to the bottom side.
	if connected(board, 'O',
		func(row, _ int) bool { return row == 0 },
		func(row, _ int) bool { return row == height-1 },
	) {
		return "O", nil
	}

	return "", nil
}

func connected(board []string, player byte, starts, goal func(int, int) bool) bool {
	height := len(board)
	width := len(board[0])

	visited := make([][]bool, height)
	for i := range visited {
		visited[i] = make([]bool, width)
	}

	queue := make([]cell, 0, height*width)
	for row := 0; row < height; row++ {
		for col := 0; col < width; col++ {
			if board[row][col] == player && starts(row, col) {
				visited[row][col] = true
				queue = append(queue, cell{row: row, col: col})
			}
		}
	}

	// Neighbors in this offset hex grid:
	// up-left, up-right, left, right, down-left, down-right.
	directions := [][2]int{
		{-1, 0}, {-1, 1},
		{0, -1}, {0, 1},
		{1, -1}, {1, 0},
	}

	for head := 0; head < len(queue); head++ {
		current := queue[head]
		if goal(current.row, current.col) {
			return true
		}

		for _, direction := range directions {
			row := current.row + direction[0]
			col := current.col + direction[1]

			if row < 0 || row >= height || col < 0 || col >= width {
				continue
			}
			if visited[row][col] || board[row][col] != player {
				continue
			}

			visited[row][col] = true
			queue = append(queue, cell{row: row, col: col})
		}
	}

	return false
}
