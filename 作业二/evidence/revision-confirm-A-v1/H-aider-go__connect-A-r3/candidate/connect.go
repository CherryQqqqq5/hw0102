package connect

// ResultOf computes the winner of a game of Hex (Polygon / CON-TAC-TIX).
//
// Player 'O' plays from top to bottom and player 'X' plays from left to
// right. The empty string is returned when neither player has connected
// the two sides assigned to them.
func ResultOf(lines []string) (string, error) {
	// Spaces are only used for readability: drop them so that every row
	// is indexed by its column number.
	board := make([][]byte, len(lines))
	width := 0
	for i, line := range lines {
		row := make([]byte, 0, len(line))
		for j := 0; j < len(line); j++ {
			if line[j] != ' ' {
				row = append(row, line[j])
			}
		}
		board[i] = row
		if len(row) > width {
			width = len(row)
		}
	}

	height := len(board)

	if connected(board, width, height, 'X', false) {
		return "X", nil
	}
	if connected(board, width, height, 'O', true) {
		return "O", nil
	}
	return "", nil
}

type cell struct{ row, col int }

// neighbours lists the six cells touching a hexagonal field. Rows are
// shifted one position to the right for each row below, so the diagonal
// neighbours are (-1,+1) and (+1,-1).
var neighbours = [...]cell{
	{-1, 0}, {1, 0},
	{0, -1}, {0, 1},
	{-1, 1}, {1, -1},
}

// connected reports whether player has joined the two sides assigned to it.
// When topBottom is true the top and bottom rows must be joined (player 'O'),
// otherwise the left and right columns must be joined (player 'X').
func connected(board [][]byte, width, height int, player byte, topBottom bool) bool {
	if width == 0 || height == 0 {
		return false
	}

	visited := make([][]bool, height)
	for i := range visited {
		visited[i] = make([]bool, width)
	}
	queue := make([]cell, 0, width*height)

	// Seed the search with every stone of the player on the first side.
	startCount := height
	if topBottom {
		startCount = width
	}
	for i := 0; i < startCount; i++ {
		r, c := i, 0
		if topBottom {
			r, c = 0, i
		}
		if r >= height || c >= len(board[r]) {
			continue
		}
		if board[r][c] == player && !visited[r][c] {
			visited[r][c] = true
			queue = append(queue, cell{r, c})
		}
	}

	for len(queue) > 0 {
		cur := queue[0]
		queue = queue[1:]

		// Reaching the opposite side wins the game.
		if topBottom && cur.row == height-1 {
			return true
		}
		if !topBottom && cur.col == width-1 {
			return true
		}

		for _, n := range neighbours {
			r, c := cur.row+n.row, cur.col+n.col
			if r < 0 || r >= height || c < 0 || c >= len(board[r]) {
				continue
			}
			if visited[r][c] || board[r][c] != player {
				continue
			}
			visited[r][c] = true
			queue = append(queue, cell{r, c})
		}
	}
	return false
}
