#include "all_your_base.h"

#include <cstdint>
#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int from_base,
                                  const std::vector<unsigned int> &digits,
                                  unsigned int to_base) {
    if (from_base < 2 || to_base < 2) {
        throw std::invalid_argument("bases must be at least 2");
    }

    for (unsigned int digit : digits) {
        if (digit >= from_base) {
            throw std::invalid_argument("digit is invalid for the input base");
        }
    }

    std::size_t first_nonzero = 0;
    while (first_nonzero < digits.size() && digits[first_nonzero] == 0) {
        ++first_nonzero;
    }

    if (first_nonzero == digits.size()) {
        return {};
    }

    std::vector<unsigned int> converted;
    for (std::size_t i = first_nonzero; i < digits.size(); ++i) {
        std::uint64_t carry = digits[i];

        for (std::size_t j = 0; j < converted.size(); ++j) {
            const std::uint64_t value =
                static_cast<std::uint64_t>(converted[j]) * from_base + carry;
            converted[j] = static_cast<unsigned int>(value % to_base);
            carry = value / to_base;
        }

        while (carry > 0) {
            converted.push_back(static_cast<unsigned int>(carry % to_base));
            carry /= to_base;
        }
    }

    return std::vector<unsigned int>(converted.rbegin(), converted.rend());
}

}  // namespace all_your_base
