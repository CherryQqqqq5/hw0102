package connect

// ResultOf determines the winner of a game of Hex, if any.
// Player X wins by connecting the left and right sides, while player O
// wins by connecting the top and bottom sides.
func ResultOf(lines []string) (string, error) {
	if len(lines) == 0 || len(lines[0]) == 0 {
		return "", nil
	}

	if hasConnection(lines, 'X', true) {
		return "X", nil
	}
	if hasConnection(lines, 'O', false) {
		return "O", nil
	}
	return "", nil
}

func hasConnection(board []string, player byte, leftToRight bool) bool {
	height := len(board)
	width := len(board[0])

	type cell struct {
		row int
		col int
	}

	visited := make([][]bool, height)
	for i := range visited {
		visited[i] = make([]bool, width)
	}

	queue := make([]cell, 0)

	if leftToRight {
		for row := 0; row < height; row++ {
			if len(board[row]) > 0 && board[row][0] == player {
				visited[row][0] = true
				queue = append(queue, cell{row, 0})
			}
		}
	} else {
		for col := 0; col < width; col++ {
			if len(board[0]) > col && board[0][col] == player {
				visited[0][col] = true
				queue = append(queue, cell{0, col})
			}
		}
	}

	// Hexagonal neighbours in this row-offset representation:
	// left/right in the same row, and the two cells diagonally above
	// and below in the adjacent rows.
	directions := [][2]int{
		{0, -1},
		{0, 1},
		{-1, 0},
		{-1, 1},
		{1, -1},
		{1, 0},
	}

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		if leftToRight && current.col == width-1 {
			return true
		}
		if !leftToRight && current.row == height-1 {
			return true
		}

		for _, direction := range directions {
			nextRow := current.row + direction[0]
			nextCol := current.col + direction[1]

			if nextRow < 0 || nextRow >= height || nextCol < 0 || nextCol >= width {
				continue
			}
			if visited[nextRow][nextCol] {
				continue
			}
			if len(board[nextRow]) <= nextCol || board[nextRow][nextCol] != player {
				continue
			}

			visited[nextRow][nextCol] = true
			queue = append(queue, cell{nextRow, nextCol})
		}
	}

	return false
}
