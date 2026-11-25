#include "all_your_base.h"

#include <algorithm>
#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int base,
                                  const std::vector<unsigned int>& digits,
                                  unsigned int new_base) {
    if (base < 2) {
        throw std::invalid_argument("input base must be at least 2");
    }
    if (new_base < 2) {
        throw std::invalid_argument("output base must be at least 2");
    }
    for (unsigned int digit : digits) {
        if (digit >= base) {
            throw std::invalid_argument("digit is out of range for input base");
        }
    }

    // Accumulate the value in the target base, least-significant digit first,
    // so arbitrarily long inputs cannot overflow.
    std::vector<unsigned int> result;
    for (unsigned int digit : digits) {
        unsigned long long carry = digit;
        for (unsigned int& out_digit : result) {
            unsigned long long current =
                static_cast<unsigned long long>(out_digit) * base + carry;
            out_digit = static_cast<unsigned int>(current % new_base);
            carry = current / new_base;
        }
        while (carry > 0) {
            result.push_back(static_cast<unsigned int>(carry % new_base));
            carry /= new_base;
        }
    }

    // Drop leading zeros (they are trailing in little-endian order).
    while (!result.empty() && result.back() == 0) {
        result.pop_back();
    }

    std::reverse(result.begin(), result.end());
    return result;
}

}  // namespace all_your_base
