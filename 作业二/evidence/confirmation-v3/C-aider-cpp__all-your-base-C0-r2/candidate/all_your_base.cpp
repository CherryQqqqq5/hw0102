#include "all_your_base.h"

#include <stdexcept>

namespace all_your_base {

namespace {

// Remove leading zeros from a digit sequence.
void strip_leading_zeros(std::vector<unsigned int>& digits) {
    std::size_t first = 0;
    while (first < digits.size() && digits[first] == 0) {
        ++first;
    }
    digits.erase(digits.begin(), digits.begin() + static_cast<std::ptrdiff_t>(first));
}

}  // namespace

// Converts a number, given as a sequence of digits in `input_base`, into the
// equivalent sequence of digits in `output_base`.
//
// The conversion is done entirely with digit arithmetic ("long division" of the
// digit sequence by the output base) so that arbitrary-length inputs can be
// handled without overflowing any fixed-width integer type.
std::vector<unsigned int> convert(int input_base,
                                  const std::vector<unsigned int>& digits,
                                  int output_base) {
    if (input_base < 2) {
        throw std::invalid_argument("input base must be at least 2");
    }
    if (output_base < 2) {
        throw std::invalid_argument("output base must be at least 2");
    }

    std::vector<unsigned int> current(digits);
    for (unsigned int digit : current) {
        if (digit >= static_cast<unsigned int>(input_base)) {
            throw std::invalid_argument("digit is not valid for the input base");
        }
    }
    strip_leading_zeros(current);

    // Zero (or an empty digit list) has no representation besides the empty
    // sequence, matching the exercise's expectations.
    std::vector<unsigned int> result;
    const auto in = static_cast<unsigned long long>(input_base);
    const auto out = static_cast<unsigned long long>(output_base);

    while (!current.empty()) {
        unsigned long long remainder = 0;
        for (unsigned int& digit : current) {
            const unsigned long long cur = remainder * in + digit;
            digit = static_cast<unsigned int>(cur / out);
            remainder = cur % out;
        }
        result.insert(result.begin(), static_cast<unsigned int>(remainder));
        strip_leading_zeros(current);
    }

    return result;
}

}  // namespace all_your_base
