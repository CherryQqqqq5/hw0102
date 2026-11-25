#include "all_your_base.h"

#include <algorithm>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int in_base,
                                  const std::vector<unsigned int>& in_digits,
                                  unsigned int out_base) {
    if (in_base < 2u) {
        throw std::invalid_argument("input base must be at least 2");
    }
    if (out_base < 2u) {
        throw std::invalid_argument("output base must be at least 2");
    }

    // Accumulate the value directly as digits in the output base,
    // least-significant digit first.  This avoids any fixed-width overflow
    // for arbitrarily long input sequences.
    std::vector<unsigned int> result;

    for (unsigned int digit : in_digits) {
        if (digit >= in_base) {
            throw std::invalid_argument("digit out of range for input base");
        }

        unsigned long long carry = digit;
        for (unsigned int& out_digit : result) {
            unsigned long long product =
                static_cast<unsigned long long>(out_digit) * in_base + carry;
            out_digit = static_cast<unsigned int>(product % out_base);
            carry = product / out_base;
        }
        while (carry > 0) {
            result.push_back(static_cast<unsigned int>(carry % out_base));
            carry /= out_base;
        }
    }

    // Strip leading zeros (stored at the back in LSB-first order).
    while (!result.empty() && result.back() == 0u) {
        result.pop_back();
    }
    std::reverse(result.begin(), result.end());
    return result;
}

}  // namespace all_your_base
