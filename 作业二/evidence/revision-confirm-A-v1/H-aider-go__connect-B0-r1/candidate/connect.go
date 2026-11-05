package connect

import "strings"

func ResultOf(lines []string) (string, error) {
	board := make([]string, len(lines))
	cols := 0
	for i, line := range lines {
		board[i] = strings.ReplaceAll(line, " ", "")
		if len(board[i]) > cols {
			cols = len(board[i])
		}
	}

	if len(board) == 0 || cols == 0 {
		return "", nil
	}

	// Neighbors in the compact (space-free) representation:
	// same row left/right, row above at same column and column+1,
	// and row below at column-1 and same column.
	dr := []int{-1, -1, 0, 0, 1, 1}
	dc := []int{0, 1, -1, 1, -1, 0}

	visited := make([][]bool, len(board))
	for r := range visited {
		visited[r] = make([]bool, cols)
	}

	win := func(player byte, starts [][2]int, goal func(r, c int) bool) bool {
		for r := range visited {
			for c := range visited[r] {
				visited[r][c] = false
			}
		}

		queue := make([][2]int, 0, len(board)*cols)
		for _, start := range starts {
			r, c := start[0], start[1]
			if r >= 0 && r < len(board) && c >= 0 && c < len(board[r]) &&
				board[r][c] == player && !visited[r][c] {
				visited[r][c] = true
				queue = append(queue, start)
			}
		}

		for head := 0; head < len(queue); head++ {
			r, c := queue[head][0], queue[head][1]
			if goal(r, c) {
				return true
			}

			for k := 0; k < 6; k++ {
				nr, nc := r+dr[k], c+dc[k]
				if nr >= 0 && nr < len(board) && nc >= 0 && nc < len(board[nr]) &&
					board[nr][nc] == player && !visited[nr][nc] {
					visited[nr][nc] = true
					queue = append(queue, [2]int{nr, nc})
				}
			}
		}

		return false
	}

	xStarts := make([][2]int, 0, len(board))
	for r := range board {
		if len(board[r]) > 0 {
			xStarts = append(xStarts, [2]int{r, 0})
		}
	}
	if win('X', xStarts, func(_, c int) bool {
		return c == cols-1
	}) {
		return "X", nil
	}

	oStarts := make([][2]int, 0, len(board[0]))
	for c := range board[0] {
		oStarts = append(oStarts, [2]int{0, c})
	}
	if win('O', oStarts, func(r, _ int) bool {
		return r == len(board)-1
	}) {
		return "O", nil
	}

	return "", nil
}
