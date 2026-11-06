#include "all_your_base.h"

#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int in_base,
                                   const std::vector<unsigned int>& in_digits,
                                   unsigned int out_base) {
    if (in_base < 2) {
        throw std::invalid_argument("input base must be at least 2");
    }
    if (out_base < 2) {
        throw std::invalid_argument("output base must be at least 2");
    }

    unsigned long long value = 0;
    for (auto digit : in_digits) {
        if (digit >= in_base) {
            throw std::invalid_argument("digit is out of range for input base");
        }
        value = value * in_base + digit;
    }

    std::vector<unsigned int> out_digits;
    while (value > 0) {
        out_digits.insert(out_digits.begin(),
                          static_cast<unsigned int>(value % out_base));
        value /= out_base;
    }

    return out_digits;
}

}  // namespace all_your_base
