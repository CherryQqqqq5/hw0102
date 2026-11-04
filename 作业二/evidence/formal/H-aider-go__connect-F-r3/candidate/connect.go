package connect

// ResultOf determines the winner of a game of Hex / Polygon.
// "X" plays from left to right, "O" plays from top to bottom.
// It returns "X", "O" or "" when nobody has won.
func ResultOf(lines []string) (string, error) {
	grid := make([][]rune, len(lines))
	for i, line := range lines {
		row := make([]rune, 0, len(line))
		for _, ch := range line {
			if ch != ' ' {
				row = append(row, ch)
			}
		}
		grid[i] = row
	}

	if wins(grid, 'X') {
		return "X", nil
	}
	if wins(grid, 'O') {
		return "O", nil
	}
	return "", nil
}

// wins reports whether player p has connected their two sides.
func wins(grid [][]rune, p rune) bool {
	rows := len(grid)
	if rows == 0 {
		return false
	}

	type cell struct{ r, c int }

	visited := make([][]bool, rows)
	for i := range visited {
		visited[i] = make([]bool, len(grid[i]))
	}

	var queue []cell
	// X connects the left and right edges, O connects the top and bottom edges.
	for r := 0; r < rows; r++ {
		for c := 0; c < len(grid[r]); c++ {
			if grid[r][c] != p {
				continue
			}
			if (p == 'X' && c == 0) || (p == 'O' && r == 0) {
				visited[r][c] = true
				queue = append(queue, cell{r, c})
			}
		}
	}

	// Each row is offset one column to the right relative to the row above,
	// so the neighbours of (r, c) are the horizontal ones plus
	// (r-1, c), (r-1, c+1), (r+1, c), (r+1, c-1).
	dirs := [6][2]int{
		{0, -1}, {0, 1},
		{-1, 0}, {-1, 1},
		{1, 0}, {1, -1},
	}

	for len(queue) > 0 {
		cur := queue[0]
		queue = queue[1:]

		if p == 'X' && cur.c == len(grid[cur.r])-1 {
			return true
		}
		if p == 'O' && cur.r == rows-1 {
			return true
		}

		for _, d := range dirs {
			nr, nc := cur.r+d[0], cur.c+d[1]
			if nr < 0 || nr >= rows || nc < 0 || nc >= len(grid[nr]) {
				continue
			}
			if visited[nr][nc] || grid[nr][nc] != p {
				continue
			}
			visited[nr][nc] = true
			queue = append(queue, cell{nr, nc})
		}
	}

	return false
}
