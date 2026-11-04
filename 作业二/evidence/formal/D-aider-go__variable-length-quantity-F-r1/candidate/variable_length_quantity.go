package variablelengthquantity

import "errors"

// EncodeVarint encodes a slice of uint32 values using variable length quantity
// encoding.
func EncodeVarint(input []uint32) []byte {
	out := make([]byte, 0, len(input)*2)

	for _, n := range input {
		var encoded [5]byte
		i := len(encoded) - 1
		encoded[i] = byte(n & 0x7f)
		n >>= 7

		for n > 0 {
			i--
			encoded[i] = byte(n&0x7f) | 0x80
			n >>= 7
		}

		out = append(out, encoded[i:]...)
	}

	return out
}

// DecodeVarint decodes a byte slice containing variable length quantity
// encoded uint32 values.
func DecodeVarint(input []byte) ([]uint32, error) {
	var out []uint32
	var value uint64
	count := 0

	for _, b := range input {
		value = (value << 7) | uint64(b&0x7f)
		count++

		if count > 5 || value > 0xffffffff {
			return nil, errors.New("invalid varint")
		}

		if b&0x80 == 0 {
			out = append(out, uint32(value))
			value = 0
			count = 0
		}
	}

	if count != 0 {
		return nil, errors.New("incomplete varint")
	}

	return out, nil
}
