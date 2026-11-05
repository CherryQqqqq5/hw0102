package variablelengthquantity

// EncodeVarint encodes each 32-bit unsigned integer in input as a
// variable length quantity. Each output byte carries 7 significant bits,
// with bit #7 set on every byte except the last one of each value.
func EncodeVarint(input []uint32) []byte {
	out := make([]byte, 0, len(input)*5)
	for _, n := range input {
		// Collect 7-bit groups, least significant first.
		var buf [5]byte
		i := 0
		for {
			buf[i] = byte(n & 0x7f)
			n >>= 7
			i++
			if n == 0 {
				break
			}
		}
		// Emit most significant group first; set continuation bit on
		// all but the final byte.
		for j := i - 1; j >= 0; j-- {
			b := buf[j]
			if j != 0 {
				b |= 0x80
			}
			out = append(out, b)
		}
	}
	return out
}

// DecodeVarint decodes a sequence of variable length quantities into
// 32-bit unsigned integers. It returns an error if the input ends in the
// middle of a value or if a value does not fit in 32 bits.
func DecodeVarint(input []byte) ([]uint32, error) {
	out := make([]uint32, 0, len(input))
	var value uint32
	inProgress := false
	for _, b := range input {
		// Groups arrive most significant first, so shift the accumulated
		// value left by 7 bits before appending the new 7-bit group.
		if value > 0x01ffffff {
			return nil, errOverflow
		}
		value = value<<7 | uint32(b&0x7f)
		if b&0x80 != 0 {
			inProgress = true
			continue
		}
		out = append(out, value)
		value = 0
		inProgress = false
	}
	if inProgress {
		return nil, errIncomplete
	}
	return out, nil
}

type vlqError string

func (e vlqError) Error() string { return string(e) }

const (
	errIncomplete vlqError = "incomplete variable length quantity sequence"
	errOverflow   vlqError = "variable length quantity overflows 32 bits"
)
