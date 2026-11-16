#include "all_your_base.h"

#include <cstdint>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int input_base,
                                  const std::vector<unsigned int>& input_digits,
                                  unsigned int output_base) {
    if (input_base < 2 || output_base < 2) {
        throw std::invalid_argument("bases must be at least 2");
    }

    for (unsigned int digit : input_digits) {
        if (digit >= input_base) {
            throw std::invalid_argument("digit is not valid in the input base");
        }
    }

    std::size_t first_nonzero = 0;
    while (first_nonzero < input_digits.size() &&
           input_digits[first_nonzero] == 0) {
        ++first_nonzero;
    }
    if (first_nonzero == input_digits.size()) {
        return {};
    }

    std::vector<unsigned int> dividend(input_digits.begin() + first_nonzero,
                                       input_digits.end());
    std::vector<unsigned int> result;

    // Repeatedly divide the source representation by the target base. Each
    // remainder is one output digit; the last remainder is the most
    // significant digit, so reverse them at the end.
    while (!dividend.empty()) {
        std::uint64_t remainder = 0;
        std::vector<unsigned int> quotient;
        quotient.reserve(dividend.size());

        for (unsigned int digit : dividend) {
            const std::uint64_t value =
                remainder * static_cast<std::uint64_t>(input_base) + digit;
            const unsigned int quotient_digit =
                static_cast<unsigned int>(value / output_base);
            remainder = value % output_base;

            if (!quotient.empty() || quotient_digit != 0) {
                quotient.push_back(quotient_digit);
            }
        }

        result.push_back(static_cast<unsigned int>(remainder));
        dividend.swap(quotient);
    }

    return std::vector<unsigned int>(result.rbegin(), result.rend());
}

}  // namespace all_your_base
