package variablelengthquantity

import "errors"

// EncodeVarint encodes a slice of uint32 values into a VLQ byte stream.
func EncodeVarint(input []uint32) []byte {
	out := make([]byte, 0, len(input)*2)
	for _, v := range input {
		var buf [5]byte
		n := 0
		// Emit least significant 7-bit groups first, then reverse.
		for {
			buf[n] = byte(v & 0x7f)
			n++
			v >>= 7
			if v == 0 {
				break
			}
		}
		for i := n - 1; i >= 0; i-- {
			b := buf[i]
			if i != 0 {
				b |= 0x80
			}
			out = append(out, b)
		}
	}
	return out
}

// DecodeVarint decodes a VLQ byte stream into a slice of uint32 values.
func DecodeVarint(input []byte) ([]uint32, error) {
	var out []uint32
	var value uint32
	pending := false
	for _, b := range input {
		// Groups arrive most-significant first.
		value = value<<7 | uint32(b&0x7f)
		if b&0x80 != 0 {
			pending = true
			continue
		}
		out = append(out, value)
		value = 0
		pending = false
	}
	if pending {
		return nil, errors.New("incomplete VLQ sequence")
	}
	return out, nil
}
