package connect

// ResultOf returns the winner of a game of Hex, or an empty string if there is
// no winner. Player X wins by connecting the left and right sides, while player
// O wins by connecting the top and bottom sides.
func ResultOf(lines []string) (string, error) {
	if len(lines) == 0 {
		return "", nil
	}

	// Validate the board dimensions. The supplied representation is a
	// parallelogram, so every row should have the same number of cells.
	cols := len(lines[0])
	for _, line := range lines {
		if len(line) != cols {
			return "", nil
		}
	}

	// Hexagonal neighbours in the space-stripped representation: the two
	// horizontal neighbours, the two vertical neighbours, and the two
	// diagonal neighbours that follow the parallelogram's slant.
	directions := [][2]int{
		{-1, 0}, {-1, 1},
		{0, -1}, {0, 1},
		{1, -1}, {1, 0},
	}

	connected := func(player byte, starts [][2]int, goal func(r, c int) bool) bool {
		visited := make([][]bool, len(lines))
		for i := range visited {
			visited[i] = make([]bool, cols)
		}

		queue := make([][2]int, 0, len(lines)*cols)
		for _, start := range starts {
			r, c := start[0], start[1]
			if r >= 0 && r < len(lines) && c >= 0 && c < cols &&
				lines[r][c] == player && !visited[r][c] {
				visited[r][c] = true
				queue = append(queue, start)
			}
		}

		for len(queue) > 0 {
			cell := queue[0]
			queue = queue[1:]
			r, c := cell[0], cell[1]

			if goal(r, c) {
				return true
			}

			for _, d := range directions {
				nr, nc := r+d[0], c+d[1]
				if nr >= 0 && nr < len(lines) && nc >= 0 && nc < cols &&
					!visited[nr][nc] && lines[nr][nc] == player {
					visited[nr][nc] = true
					queue = append(queue, [2]int{nr, nc})
				}
			}
		}

		return false
	}

	// X connects the left and right edges.
	xStarts := make([][2]int, len(lines))
	for r := range lines {
		xStarts[r] = [2]int{r, 0}
	}
	if connected('X', xStarts, func(_, c int) bool { return c == cols-1 }) {
		return "X", nil
	}

	// O connects the top and bottom edges.
	oStarts := make([][2]int, cols)
	for c := range oStarts {
		oStarts[c] = [2]int{0, c}
	}
	if connected('O', oStarts, func(r, _ int) bool { return r == len(lines)-1 }) {
		return "O", nil
	}

	return "", nil
}
