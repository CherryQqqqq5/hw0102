package variablelengthquantity

import "errors"

// ErrIncomplete is returned when the input ends in the middle of a
// variable length quantity (i.e. the last byte still has its
// continuation bit set).
var ErrIncomplete = errors.New("incomplete variable length quantity")

// ErrOverflow is returned when a sequence does not fit in a uint32.
var ErrOverflow = errors.New("variable length quantity overflows uint32")

// EncodeVarint encodes a list of uint32 values as a variable length
// quantity byte stream.
func EncodeVarint(input []uint32) []byte {
	out := make([]byte, 0, len(input)*2)
	for _, v := range input {
		var groups [5]byte
		n := 0
		for {
			groups[n] = byte(v & 0x7f)
			n++
			v >>= 7
			if v == 0 {
				break
			}
		}
		// Emit most significant group first; all but the last get the
		// continuation bit set.
		for i := n - 1; i > 0; i-- {
			out = append(out, groups[i]|0x80)
		}
		out = append(out, groups[0])
	}
	return out
}

// DecodeVarint decodes a variable length quantity byte stream into a
// list of uint32 values.
func DecodeVarint(input []byte) ([]uint32, error) {
	const maxShifted = ^uint32(0) >> 7 // largest value that may still be shifted left by 7

	var out []uint32
	var value uint32
	count := 0

	for _, b := range input {
		if value > maxShifted {
			return nil, ErrOverflow
		}
		value = value<<7 | uint32(b&0x7f)
		count++
		if b&0x80 != 0 {
			continue
		}
		out = append(out, value)
		value = 0
		count = 0
	}

	if count != 0 {
		return nil, ErrIncomplete
	}
	return out, nil
}
