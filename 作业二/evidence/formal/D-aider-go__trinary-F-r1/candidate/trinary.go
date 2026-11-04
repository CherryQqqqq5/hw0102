package trinary

import (
	"errors"
	"math"
)

var (
	errInvalidDigit = errors.New("trinary: invalid digit")
	errOverflow     = errors.New("trinary: value overflows int64")
)

// ParseTrinary converts a string of trinary digits to its decimal value,
// built up from first principles (no standard library conversion).
// Strings containing symbols other than '0', '1' and '2', or whose value
// does not fit in an int64, return an error.
func ParseTrinary(arg string) (int64, error) {
	var result int64
	for i := 0; i < len(arg); i++ {
		c := arg[i]
		if c < '0' || c > '2' {
			return 0, errInvalidDigit
		}
		digit := int64(c - '0')
		// Detect overflow before multiplying by the base.
		if result > (math.MaxInt64-digit)/3 {
			return 0, errOverflow
		}
		result = result*3 + digit
	}
	return result, nil
}
