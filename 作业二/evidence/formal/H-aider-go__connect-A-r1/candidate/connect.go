package connect

import "errors"

// ResultOf determines the winner of a game of Hex ("Polygon"/CON-TAC-TIX).
//
// Player "X" wins by connecting the left and right sides of the board.
// Player "O" wins by connecting the top and bottom sides of the board.
//
// The board is supplied as rows of characters without separators, where each
// successive row is shifted one column to the right relative to the previous
// one (that visual offset defines the hexagonal adjacency).
func ResultOf(lines []string) (string, error) {
	height := len(lines)
	if height == 0 {
		return "", nil
	}
	width := len(lines[0])
	if width == 0 {
		return "", nil
	}

	grid := make([][]byte, height)
	for r, line := range lines {
		if len(line) != width {
			return "", errors.New("connect: board rows have inconsistent lengths")
		}
		grid[r] = []byte(line)
		for _, ch := range grid[r] {
			if ch != 'X' && ch != 'O' && ch != '.' {
				return "", errors.New("connect: invalid character in board")
			}
		}
	}

	if hasPath(grid, 'X') {
		return "X", nil
	}
	if hasPath(grid, 'O') {
		return "O", nil
	}
	return "", nil
}

// hasPath reports whether player's stones form a connected chain between the
// two sides that player owns.
func hasPath(grid [][]byte, player byte) bool {
	height := len(grid)
	width := len(grid[0])

	// Hexagonal neighbours for a board where each row is offset one column to
	// the right of the row above it.
	dr := [6]int{0, 0, -1, -1, 1, 1}
	dc := [6]int{-1, 1, 0, 1, -1, 0}

	visited := make([][]bool, height)
	for r := range visited {
		visited[r] = make([]bool, width)
	}

	type cell struct{ r, c int }
	queue := make([]cell, 0, height*width)

	// X starts on the left edge and aims for the right edge.
	// O starts on the top edge and aims for the bottom edge.
	if player == 'X' {
		for r := 0; r < height; r++ {
			if grid[r][0] == player {
				visited[r][0] = true
				queue = append(queue, cell{r, 0})
			}
		}
	} else {
		for c := 0; c < width; c++ {
			if grid[0][c] == player {
				visited[0][c] = true
				queue = append(queue, cell{0, c})
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

		for i := 0; i < 6; i++ {
			nr, nc := cur.r+dr[i], cur.c+dc[i]
			if nr < 0 || nr >= height || nc < 0 || nc >= width {
				continue
			}
			if visited[nr][nc] || grid[nr][nc] != player {
				continue
			}
			visited[nr][nc] = true
			queue = append(queue, cell{nr, nc})
		}
	}

	return false
}
