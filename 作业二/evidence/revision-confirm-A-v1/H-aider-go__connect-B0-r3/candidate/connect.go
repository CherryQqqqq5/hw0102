package connect

import "fmt"

type hexCell struct {
	row, col int
}

// Neighbors of a cell on a hex grid represented as a parallelogram.
var hexDirections = [...]hexCell{
	{-1, 0}, {1, 0}, {0, -1}, {0, 1}, {-1, 1}, {1, -1},
}

func ResultOf(lines []string) (string, error) {
	height := len(lines)
	if height == 0 {
		return "", nil
	}

	width := len(lines[0])
	for _, line := range lines {
		if len(line) != width {
			return "", fmt.Errorf("invalid board: all rows must have the same width")
		}
	}
	if width == 0 {
		return "", nil
	}

	if hasConnection(lines, 'X', height, width) {
		return "X", nil
	}
	if hasConnection(lines, 'O', height, width) {
		return "O", nil
	}
	return "", nil
}

func hasConnection(board []string, player byte, height, width int) bool {
	visited := make([][]bool, height)
	for i := range visited {
		visited[i] = make([]bool, width)
	}

	queue := make([]hexCell, 0, height*width)
	add := func(row, col int) {
		if row < 0 || row >= height || col < 0 || col >= width {
			return
		}
		if visited[row][col] || board[row][col] != player {
			return
		}
		visited[row][col] = true
		queue = append(queue, hexCell{row, col})
	}

	if player == 'X' {
		// X starts on the left edge and must reach the right edge.
		for row := 0; row < height; row++ {
			add(row, 0)
		}
	} else {
		// O starts on the top edge and must reach the bottom edge.
		for col := 0; col < width; col++ {
			add(0, col)
		}
	}

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		if player == 'X' && current.col == width-1 {
			return true
		}
		if player == 'O' && current.row == height-1 {
			return true
		}

		for _, d := range hexDirections {
			add(current.row+d.row, current.col+d.col)
		}
	}

	return false
}
