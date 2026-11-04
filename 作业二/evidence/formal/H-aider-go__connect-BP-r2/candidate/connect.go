package connect

// ResultOf determines the winner of a game of Hex/Polygon.
// "O" wins by connecting top to bottom, "X" by connecting left to right.
func ResultOf(lines []string) (string, error) {
	grid := make([][]byte, len(lines))
	for i, line := range lines {
		row := make([]byte, 0, len(line))
		for j := 0; j < len(line); j++ {
			if line[j] != ' ' {
				row = append(row, line[j])
			}
		}
		grid[i] = row
	}

	if connected(grid, 'X',
		func(r, c int) bool { return c == 0 },
		func(r, c int) bool { return c == len(grid[r])-1 }) {
		return "X", nil
	}
	if connected(grid, 'O',
		func(r, c int) bool { return r == 0 },
		func(r, c int) bool { return r == len(grid)-1 }) {
		return "O", nil
	}
	return "", nil
}

// connected reports whether player has a path of own stones from any cell
// satisfying start to any cell satisfying goal.
func connected(grid [][]byte, player byte, start, goal func(r, c int) bool) bool {
	visited := make([][]bool, len(grid))
	for i := range grid {
		visited[i] = make([]bool, len(grid[i]))
	}

	var dfs func(r, c int) bool
	dfs = func(r, c int) bool {
		if r < 0 || r >= len(grid) || c < 0 || c >= len(grid[r]) {
			return false
		}
		if visited[r][c] || grid[r][c] != player {
			return false
		}
		visited[r][c] = true
		if goal(r, c) {
			return true
		}
		// Hex neighbours for rows indented progressively to the right.
		return dfs(r, c-1) || dfs(r, c+1) ||
			dfs(r-1, c) || dfs(r-1, c+1) ||
			dfs(r+1, c-1) || dfs(r+1, c)
	}

	for r := range grid {
		for c := range grid[r] {
			if grid[r][c] == player && start(r, c) {
				if dfs(r, c) {
					return true
				}
			}
		}
	}
	return false
}
