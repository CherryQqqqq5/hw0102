package connect

// ResultOf determines the winner of a Hex/Polygon game.
//
// Player "O" plays top to bottom, player "X" plays left to right.
// Boards that come in have already had their formatting spaces removed,
// so they are rectangular grids. Because each successive row is printed
// shifted right by half a cell, two cells (r,c) and (r',c') are adjacent
// in the (r,c+-1), (r+-1,c), (r-1,c+1), (r+1,c-1) sense.
func ResultOf(lines []string) (string, error) {
	if len(lines) == 0 {
		return "", nil
	}

	height := len(lines)
	width := 0
	for _, l := range lines {
		if len(l) > width {
			width = len(l)
		}
	}
	if width == 0 {
		return "", nil
	}

	at := func(r, c int) byte {
		if r < 0 || r >= height || c < 0 || c >= len(lines[r]) {
			return 0
		}
		return lines[r][c]
	}

	neighbors := [6][2]int{
		{-1, 0}, {1, 0},
		{0, -1}, {0, 1},
		{-1, 1}, {1, -1},
	}

	// wins reports whether the given player connects its two sides.
	wins := func(player byte, start func(r, c int) bool, target func(r, c int) bool) bool {
		visited := make([][]bool, height)
		for i := range visited {
			visited[i] = make([]bool, width)
		}
		queue := make([][2]int, 0, height*width)
		for r := 0; r < height; r++ {
			for c := 0; c < width; c++ {
				if at(r, c) == player && start(r, c) {
					visited[r][c] = true
					queue = append(queue, [2]int{r, c})
				}
			}
		}
		for len(queue) > 0 {
			cur := queue[0]
			queue = queue[1:]
			r, c := cur[0], cur[1]
			if target(r, c) {
				return true
			}
			for _, d := range neighbors {
				nr, nc := r+d[0], c+d[1]
				if nr < 0 || nr >= height || nc < 0 || nc >= width {
					continue
				}
				if visited[nr][nc] || at(nr, nc) != player {
					continue
				}
				visited[nr][nc] = true
				queue = append(queue, [2]int{nr, nc})
			}
		}
		return false
	}

	// X connects left (c == 0) to right (c == width-1).
	if wins('X',
		func(r, c int) bool { return c == 0 },
		func(r, c int) bool { return c == width-1 }) {
		return "X", nil
	}

	// O connects top (r == 0) to bottom (r == height-1).
	if wins('O',
		func(r, c int) bool { return r == 0 },
		func(r, c int) bool { return r == height-1 }) {
		return "O", nil
	}

	return "", nil
}
