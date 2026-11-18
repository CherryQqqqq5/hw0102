#include "all_your_base.h"

#include <cstdint>
#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int from_base,
                                  const std::vector<unsigned int>& in_digits,
                                  unsigned int to_base) {
    if (from_base < 2 || to_base < 2) {
        throw std::invalid_argument("bases must be at least 2");
    }

    std::vector<unsigned int> dividend;
    dividend.reserve(in_digits.size());

    bool leading_zero = true;
    for (unsigned int digit : in_digits) {
        if (digit >= from_base) {
            throw std::invalid_argument("digit is not valid in the source base");
        }
        if (leading_zero && digit == 0) {
            continue;
        }
        leading_zero = false;
        dividend.push_back(digit);
    }

    std::vector<unsigned int> result;
    while (!dividend.empty()) {
        std::vector<unsigned int> quotient;
        quotient.reserve(dividend.size());

        std::uint64_t remainder = 0;
        for (unsigned int digit : dividend) {
            const std::uint64_t value = remainder * from_base + digit;
            const std::uint64_t quotient_digit = value / to_base;
            remainder = value % to_base;
            if (quotient_digit != 0 || !quotient.empty()) {
                quotient.push_back(static_cast<unsigned int>(quotient_digit));
            }
        }

        result.push_back(static_cast<unsigned int>(remainder));
        dividend.swap(quotient);
    }

    std::vector<unsigned int> converted;
    converted.reserve(result.size());
    for (auto it = result.rbegin(); it != result.rend(); ++it) {
        converted.push_back(*it);
    }
    return converted;
}

}  // namespace all_your_base
