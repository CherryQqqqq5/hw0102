#include "all_your_base.h"

#include <algorithm>
#include <cstdint>

namespace all_your_base {
namespace {

using digit_type = unsigned int;

void trim_leading_zeros(std::vector<digit_type>& digits) {
    std::size_t first_nonzero = 0;
    while (first_nonzero < digits.size() && digits[first_nonzero] == 0) {
        ++first_nonzero;
    }
    digits.erase(digits.begin(),
                 digits.begin() + static_cast<std::vector<digit_type>::difference_type>(first_nonzero));
}

}  // namespace

std::vector<digit_type> convert(int input_base,
                                const std::vector<digit_type>& input_digits,
                                int output_base) {
    if (input_base < 2 || output_base < 2) {
        throw std::invalid_argument("Base must be greater than one");
    }

    const auto maximum_digit = static_cast<digit_type>(input_base);
    for (const digit_type digit : input_digits) {
        if (digit >= maximum_digit) {
            throw std::invalid_argument("Digit is not valid for the input base");
        }
    }

    std::vector<digit_type> working_digits = input_digits;
    trim_leading_zeros(working_digits);

    std::vector<digit_type> output_digits;
    const auto from_base = static_cast<std::uint64_t>(input_base);
    const auto to_base = static_cast<std::uint64_t>(output_base);

    while (!working_digits.empty()) {
        std::uint64_t remainder = 0;
        std::vector<digit_type> quotient;
        quotient.reserve(working_digits.size());

        for (const digit_type digit : working_digits) {
            const std::uint64_t current = remainder * from_base + static_cast<std::uint64_t>(digit);
            const auto quotient_digit = static_cast<digit_type>(current / to_base);
            remainder = current % to_base;

            if (!quotient.empty() || quotient_digit != 0) {
                quotient.push_back(quotient_digit);
            }
        }

        output_digits.push_back(static_cast<digit_type>(remainder));
        working_digits.swap(quotient);
    }

    std::reverse(output_digits.begin(), output_digits.end());
    return output_digits;
}

}  // namespace all_your_base
