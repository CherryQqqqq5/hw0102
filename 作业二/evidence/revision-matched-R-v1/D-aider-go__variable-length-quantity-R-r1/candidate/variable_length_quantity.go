package variablelengthquantity

import "errors"

// ErrIncompleteSequence is returned when the input ends mid-varint.
var ErrIncompleteSequence = errors.New("incomplete sequence")

// EncodeVarint encodes each uint32 as a variable length quantity.
// The first 7 bits of every byte are significant; bit 7 is set on all
// bytes except the last one of each value.
func EncodeVarint(input []uint32) []byte {
	out := make([]byte, 0, len(input)*2)
	for _, n := range input {
		var buf [5]byte
		i := 4
		buf[i] = byte(n & 0x7f)
		n >>= 7
		for n > 0 {
			i--
			buf[i] = byte(n&0x7f) | 0x80
			n >>= 7
		}
		out = append(out, buf[i:]...)
	}
	return out
}

// DecodeVarint decodes a sequence of variable length quantities.
// It errors if the input ends in the middle of a value.
func DecodeVarint(input []byte) ([]uint32, error) {
	out := make([]uint32, 0, len(input))
	var val uint32
	for _, b := range input {
		val = val<<7 | uint32(b&0x7f)
		if b&0x80 == 0 {
			out = append(out, val)
			val = 0
		}
	}
	if len(input) > 0 && input[len(input)-1]&0x80 != 0 {
		return nil, ErrIncompleteSequence
	}
	return out, nil
}
