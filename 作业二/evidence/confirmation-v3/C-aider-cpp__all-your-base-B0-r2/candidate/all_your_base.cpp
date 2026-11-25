#include "all_your_base.h"

#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int from_base,
                                  const std::vector<unsigned int>& digits,
                                  unsigned int to_base) {
    if (from_base < 2 || to_base < 2) {
        throw std::invalid_argument("base must be at least 2");
    }

    // Accumulate the value represented by the input digits.
    unsigned long long value = 0;
    for (unsigned int digit : digits) {
        if (digit >= from_base) {
            throw std::invalid_argument("digit is not valid in the input base");
        }
        value = value * from_base + digit;
    }

    // Zero (or no digits) is represented by an empty digit sequence.
    if (value == 0) {
        return {};
    }

    // Produce the digits in the target base, least significant first.
    std::vector<unsigned int> result;
    while (value > 0) {
        result.push_back(static_cast<unsigned int>(value % to_base));
        value /= to_base;
    }

    // Reverse into most significant first order.
    return std::vector<unsigned int>(result.rbegin(), result.rend());
}

}  // namespace all_your_base
