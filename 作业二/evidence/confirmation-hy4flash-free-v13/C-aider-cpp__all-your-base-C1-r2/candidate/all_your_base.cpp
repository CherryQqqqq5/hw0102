#include "all_your_base.h"

#include <algorithm>
#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int from_base,
                                  const std::vector<unsigned int>& in_digits,
                                  unsigned int to_base) {
    if (from_base < 2 || to_base < 2) {
        throw std::invalid_argument("bases must be at least 2");
    }

    std::vector<unsigned int> digits;
    bool found_nonzero = false;
    for (const unsigned int digit : in_digits) {
        if (digit >= from_base) {
            throw std::invalid_argument("digit is invalid for the input base");
        }
        if (digit != 0 || found_nonzero) {
            digits.push_back(digit);
            if (digit != 0) {
                found_nonzero = true;
            }
        }
    }

    if (!found_nonzero) {
        return {};
    }

    std::vector<unsigned int> output;
    while (!digits.empty()) {
        unsigned int remainder = 0;
        std::vector<unsigned int> quotient;
        bool started = false;

        for (const unsigned int digit : digits) {
            const unsigned long long dividend =
                static_cast<unsigned long long>(remainder) * from_base + digit;
            const unsigned int quotient_digit =
                static_cast<unsigned int>(dividend / to_base);
            remainder = static_cast<unsigned int>(dividend % to_base);

            if (quotient_digit != 0 || started) {
                quotient.push_back(quotient_digit);
                started = true;
            }
        }

        output.push_back(remainder);
        digits.swap(quotient);
    }

    std::reverse(output.begin(), output.end());
    return output;
}

}  // namespace all_your_base
