package connect

// ResultOf determines the winner of a Hex/Polygon game. Player X wins by
// connecting the left and right sides; player O wins by connecting the top
// and bottom sides. An empty string is returned when nobody has won.
//
// The board may be given either with the leading indentation that visually
// represents the hexagonal layout or with all spaces removed, so spaces are
// stripped before the search is performed.
func ResultOf(lines []string) (string, error) {
	board := make([][]byte, len(lines))
	for i, line := range lines {
		board[i] = []byte(stripSpaces(line))
	}

	if hasConnection(board, 'X', true) {
		return "X", nil
	}
	if hasConnection(board, 'O', false) {
		return "O", nil
	}
	return "", nil
}

func stripSpaces(line string) string {
	out := make([]byte, 0, len(line))
	for i := 0; i < len(line); i++ {
		if line[i] != ' ' {
			out = append(out, line[i])
		}
	}
	return string(out)
}

// hasConnection reports whether player's stones form a path joining the two
// opposite sides of the board. When leftToRight is true the search runs from
// the left edge to the right edge (X); otherwise from the top edge to the
// bottom edge (O).
func hasConnection(board [][]byte, player byte, leftToRight bool) bool {
	rows := len(board)
	if rows == 0 || len(board[0]) == 0 {
		return false
	}

	cols := len(board[0])
	for _, row := range board {
		if len(row) != cols {
			return false
		}
	}

	visited := make([][]bool, rows)
	for i := range visited {
		visited[i] = make([]bool, cols)
	}

	type cell struct {
		row, col int
	}
	queue := make([]cell, 0)

	if leftToRight {
		for r := 0; r < rows; r++ {
			if board[r][0] == player {
				visited[r][0] = true
				queue = append(queue, cell{r, 0})
			}
		}
	} else {
		for c := 0; c < cols; c++ {
			if board[0][c] == player {
				visited[0][c] = true
				queue = append(queue, cell{0, c})
			}
		}
	}

	// Neighbours in a hex grid laid out row by row with rows shifted right.
	directions := [][2]int{
		{-1, 0}, {-1, 1},
		{0, -1}, {0, 1},
		{1, -1}, {1, 0},
	}

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		if leftToRight && current.col == cols-1 {
			return true
		}
		if !leftToRight && current.row == rows-1 {
			return true
		}

		for _, d := range directions {
			nr := current.row + d[0]
			nc := current.col + d[1]
			if nr < 0 || nr >= rows || nc < 0 || nc >= cols {
				continue
			}
			if visited[nr][nc] || board[nr][nc] != player {
				continue
			}
			visited[nr][nc] = true
			queue = append(queue, cell{nr, nc})
		}
	}

	return false
}
