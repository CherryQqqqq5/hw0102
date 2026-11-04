package connect

// ResultOf determines the winner of a game of Hex/Polygon.
//
// The board is given with the indentation already removed, so every line has
// the same number of cells. "X" plays from left to right, "O" plays from top
// to bottom.
func ResultOf(lines []string) (string, error) {
	rows := len(lines)
	if rows == 0 {
		return "", nil
	}

	cols := 0
	for _, l := range lines {
		if len(l) > cols {
			cols = len(l)
		}
	}
	if cols == 0 {
		return "", nil
	}

	board := make([][]byte, rows)
	for r := 0; r < rows; r++ {
		board[r] = make([]byte, cols)
		for c := 0; c < cols; c++ {
			if c < len(lines[r]) {
				board[r][c] = lines[r][c]
			} else {
				board[r][c] = '.'
			}
		}
	}

	// With the indentation stripped, a cell (r, c) is adjacent to the cells
	// (r, c-1), (r, c+1), (r-1, c), (r-1, c+1), (r+1, c), (r+1, c-1).
	dirs := [6][2]int{
		{0, 1}, {0, -1},
		{1, 0}, {1, -1},
		{-1, 0}, {-1, 1},
	}

	wins := func(player byte, isStart, isGoal func(r, c int) bool) bool {
		visited := make([][]bool, rows)
		for r := range visited {
			visited[r] = make([]bool, cols)
		}

		queue := make([][2]int, 0, rows*cols)
		for r := 0; r < rows; r++ {
			for c := 0; c < cols; c++ {
				if board[r][c] == player && isStart(r, c) {
					visited[r][c] = true
					queue = append(queue, [2]int{r, c})
				}
			}
		}

		for len(queue) > 0 {
			cur := queue[0]
			queue = queue[1:]
			if isGoal(cur[0], cur[1]) {
				return true
			}
			for _, d := range dirs {
				nr, nc := cur[0]+d[0], cur[1]+d[1]
				if nr < 0 || nr >= rows || nc < 0 || nc >= cols {
					continue
				}
				if visited[nr][nc] || board[nr][nc] != player {
					continue
				}
				visited[nr][nc] = true
				queue = append(queue, [2]int{nr, nc})
			}
		}
		return false
	}

	if wins('X',
		func(_, c int) bool { return c == 0 },
		func(_, c int) bool { return c == cols-1 },
	) {
		return "X", nil
	}

	if wins('O',
		func(r, _ int) bool { return r == 0 },
		func(r, _ int) bool { return r == rows-1 },
	) {
		return "O", nil
	}

	return "", nil
}
