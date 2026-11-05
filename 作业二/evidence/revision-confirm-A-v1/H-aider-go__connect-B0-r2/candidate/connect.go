package connect

func ResultOf(lines []string) (string, error) {
	if wins(lines, 'X') {
		return "X", nil
	}
	if wins(lines, 'O') {
		return "O", nil
	}
	return "", nil
}

func wins(board []string, player byte) bool {
	if len(board) == 0 || len(board[0]) == 0 {
		return false
	}

	visited := make([][]bool, len(board))
	for r := range board {
		visited[r] = make([]bool, len(board[r]))
	}

	type cell struct{ r, c int }
	var stack []cell

	if player == 'X' {
		// X connects the left side to the right side.
		for r := range board {
			if board[r][0] == player {
				stack = append(stack, cell{r, 0})
				visited[r][0] = true
			}
		}
	} else {
		// O connects the top side to the bottom side.
		for c := 0; c < len(board[0]); c++ {
			if board[0][c] == player {
				stack = append(stack, cell{0, c})
				visited[0][c] = true
			}
		}
	}

	dirs := [][2]int{{0, -1}, {0, 1}, {-1, 0}, {-1, 1}, {1, 0}, {1, -1}}

	for len(stack) > 0 {
		cur := stack[len(stack)-1]
		stack = stack[:len(stack)-1]

		if (player == 'X' && cur.c == len(board[cur.r])-1) ||
			(player == 'O' && cur.r == len(board)-1) {
			return true
		}

		for _, d := range dirs {
			nr, nc := cur.r+d[0], cur.c+d[1]
			if nr < 0 || nr >= len(board) || nc < 0 || nc >= len(board[nr]) {
				continue
			}
			if !visited[nr][nc] && board[nr][nc] == player {
				visited[nr][nc] = true
				stack = append(stack, cell{nr, nc})
			}
		}
	}

	return false
}
