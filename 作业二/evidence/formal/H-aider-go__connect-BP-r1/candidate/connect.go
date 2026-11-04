package connect

func ResultOf(lines []string) (string, error) {
	if len(lines) == 0 || len(lines[0]) == 0 {
		return "", nil
	}

	height := len(lines)
	width := len(lines[0])

	hasPath := func(player byte, starts, isGoal func(int, int) bool) bool {
		visited := make([][]bool, height)
		for i := range visited {
			visited[i] = make([]bool, width)
		}

		var dfs func(int, int) bool
		dfs = func(r, c int) bool {
			if r < 0 || r >= height || c < 0 || c >= width {
				return false
			}
			if visited[r][c] || lines[r][c] != player {
				return false
			}
			visited[r][c] = true
			if isGoal(r, c) {
				return true
			}

			// The rows of a Hex board are offset; each cell has two
			// horizontal neighbours and four diagonal neighbours.
			directions := [][2]int{
				{0, 1}, {0, -1},
				{-1, 0}, {-1, 1},
				{1, 0}, {1, -1},
			}
			for _, d := range directions {
				if dfs(r+d[0], c+d[1]) {
					return true
				}
			}
			return false
		}

		for r := 0; r < height; r++ {
			for c := 0; c < width; c++ {
				if starts(r, c) && dfs(r, c) {
					return true
				}
			}
		}
		return false
	}

	if hasPath('X',
		func(r, c int) bool { return c == 0 },
		func(r, c int) bool { return c == width-1 },
	) {
		return "X", nil
	}

	if hasPath('O',
		func(r, c int) bool { return r == 0 },
		func(r, c int) bool { return r == height-1 },
	) {
		return "O", nil
	}

	return "", nil
}
