package trinary

import "errors"

const maxInt64 = int64(^uint64(0) >> 1)

// ParseTrinary converts a base-3 string to its decimal value.
// It returns an error if the string contains anything other than '0', '1', '2'
// or if the value does not fit in an int64.
func ParseTrinary(arg string) (int64, error) {
	if len(arg) == 0 {
		return 0, errors.New("empty trinary string")
	}

	var result int64
	for _, r := range arg {
		if r < '0' || r > '2' {
			return 0, errors.New("invalid trinary digit")
		}
		d := int64(r - '0')
		if result > (maxInt64-d)/3 {
			return 0, errors.New("trinary value overflows int64")
		}
		result = result*3 + d
	}
	return result, nil
}
