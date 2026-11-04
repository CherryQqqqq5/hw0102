package connect

import "errors"

func ResultOf(lines []string) (string, error) {
	if len(lines) == 0 {
		return "", nil
	}

	width := len(lines[0])
	for _, line := range lines {
		if len(line) != width {
			return "", errors.New("invalid board: rows have different lengths")
		}
	}

	if connected(lines, 'X', width, len(lines)) {
		return "X", nil
	}
	if connected(lines, 'O', width, len(lines)) {
		return "O", nil
	}
	return "", nil
}

func connected(board []string, player byte, width, height int) bool {
	if width == 0 || height == 0 {
		return false
	}

	type cell struct {
		row, col int
	}

	visited := make([][]bool, height)
	for i := range visited {
		visited[i] = make([]bool, width)
	}

	startsAtEdge := func(row, col int) bool {
		if player == 'X' {
			return col == 0
		}
		return row == 0
	}

	reachesOppositeEdge := func(row, col int) bool {
		if player == 'X' {
			return col == width-1
		}
		return row == height-1
	}

	queue := make([]cell, 0, width*height)
	for row := 0; row < height; row++ {
		for col := 0; col < width; col++ {
			if board[row][col] == player && startsAtEdge(row, col) {
				visited[row][col] = true
				queue = append(queue, cell{row, col})
			}
		}
	}

	// Hex neighbors, accounting for the half-cell horizontal offset of rows.
	rowOffsets := [...]int{-1, -1, 0, 0, 1, 1}
	colOffsets := [...]int{0, 1, -1, 1, -1, 0}

	for head := 0; head < len(queue); head++ {
		current := queue[head]
		if reachesOppositeEdge(current.row, current.col) {
			return true
		}

		for i := range rowOffsets {
			nextRow := current.row + rowOffsets[i]
			nextCol := current.col + colOffsets[i]
			if nextRow >= 0 && nextRow < height &&
				nextCol >= 0 && nextCol < width &&
				!visited[nextRow][nextCol] &&
				board[nextRow][nextCol] == player {
				visited[nextRow][nextCol] = true
				queue = append(queue, cell{nextRow, nextCol})
			}
		}
	}

	return false
}
