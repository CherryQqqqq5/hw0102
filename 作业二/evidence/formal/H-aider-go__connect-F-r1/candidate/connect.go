package connect

// ResultOf determines the winner of a game of Hex/Polygon.
// "O" plays from top to bottom, "X" plays from left to right.
func ResultOf(lines []string) (string, error) {
	if len(lines) == 0 {
		return "", nil
	}

	height := len(lines)
	width := len(lines[0])
	for _, line := range lines {
		if len(line) != width {
			return "", nil
		}
	}

	if hasPath(lines, 'X', func(r, c int) bool { return c == 0 }, func(r, c int) bool { return c == width-1 }) {
		return "X", nil
	}
	if hasPath(lines, 'O', func(r, c int) bool { return r == 0 }, func(r, c int) bool { return r == height-1 }) {
		return "O", nil
	}
	return "", nil
}

var hexDirs = [][2]int{
	{0, -1}, {0, 1},
	{-1, 0}, {-1, 1},
	{1, -1}, {1, 0},
}

// hasPath reports whether player's stones connect a start cell to a goal cell.
func hasPath(lines []string, player byte, isStart, isGoal func(r, c int) bool) bool {
	height := len(lines)
	width := len(lines[0])

	visited := make([][]bool, height)
	for i := range visited {
		visited[i] = make([]bool, width)
	}

	queue := make([][2]int, 0, height*width)
	for r := 0; r < height; r++ {
		for c := 0; c < width; c++ {
			if lines[r][c] == player && isStart(r, c) && !visited[r][c] {
				visited[r][c] = true
				queue = append(queue, [2]int{r, c})
			}
		}
	}

	for len(queue) > 0 {
		cur := queue[0]
		queue = queue[1:]
		r, c := cur[0], cur[1]
		if isGoal(r, c) {
			return true
		}
		for _, d := range hexDirs {
			nr, nc := r+d[0], c+d[1]
			if nr < 0 || nr >= height || nc < 0 || nc >= width {
				continue
			}
			if visited[nr][nc] || lines[nr][nc] != player {
				continue
			}
			visited[nr][nc] = true
			queue = append(queue, [2]int{nr, nc})
		}
	}
	return false
}
