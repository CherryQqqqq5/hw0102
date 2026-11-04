package connect

// ResultOf determines the winner of a game of Hex/Polygon.
//
// Player "X" plays from left to right (column 0 to column width-1) and
// player "O" plays from top to bottom (row 0 to row height-1). An empty
// string is returned when neither player has connected their sides.
func ResultOf(lines []string) (string, error) {
	if len(lines) == 0 || len(lines[0]) == 0 {
		return "", nil
	}

	height := len(lines)
	width := len(lines[0])

	if wins(lines, 'X', height, width) {
		return "X", nil
	}
	if wins(lines, 'O', height, width) {
		return "O", nil
	}
	return "", nil
}

type point struct {
	r, c int
}

// wins reports whether the given player has a connected path between the
// two sides they own.
func wins(board []string, player byte, height, width int) bool {
	visited := make([][]bool, height)
	for i := range visited {
		visited[i] = make([]bool, width)
	}

	// Hexagonal neighbours in this parallelogram layout: the row above is
	// shifted one cell to the left, so it connects to (r-1,c) and (r-1,c+1),
	// while the row below connects to (r+1,c-1) and (r+1,c).
	dirs := [][2]int{
		{0, -1}, {0, 1},
		{-1, 0}, {-1, 1},
		{1, -1}, {1, 0},
	}

	var queue []point

	if player == 'X' {
		// X starts on the left edge (column 0).
		for r := 0; r < height; r++ {
			if board[r][0] == player && !visited[r][0] {
				visited[r][0] = true
				queue = append(queue, point{r, 0})
			}
		}
	} else {
		// O starts on the top edge (row 0).
		for c := 0; c < width; c++ {
			if board[0][c] == player && !visited[0][c] {
				visited[0][c] = true
				queue = append(queue, point{0, c})
			}
		}
	}

	for len(queue) > 0 {
		cur := queue[0]
		queue = queue[1:]

		if player == 'X' && cur.c == width-1 {
			return true
		}
		if player == 'O' && cur.r == height-1 {
			return true
		}

		for _, d := range dirs {
			nr, nc := cur.r+d[0], cur.c+d[1]
			if nr < 0 || nr >= height || nc < 0 || nc >= width {
				continue
			}
			if visited[nr][nc] || board[nr][nc] != player {
				continue
			}
			visited[nr][nc] = true
			queue = append(queue, point{nr, nc})
		}
	}

	return false
}
