#include "all_your_base.h"

#include <algorithm>
#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int input_base,
                                  const std::vector<unsigned int>& input_digits,
                                  unsigned int output_base) {
    if (input_base < 2) {
        throw std::invalid_argument("input base must be at least 2");
    }
    if (output_base < 2) {
        throw std::invalid_argument("output base must be at least 2");
    }

    // Accumulate the value in the output base directly, most significant
    // digit first, so no fixed-width intermediate can overflow.
    std::vector<unsigned int> output_digits;
    for (unsigned int digit : input_digits) {
        if (digit >= input_base) {
            throw std::invalid_argument("digit is not valid for the input base");
        }
        unsigned long long carry = digit;
        for (std::size_t i = output_digits.size(); i-- > 0;) {
            unsigned long long cur =
                static_cast<unsigned long long>(output_digits[i]) * input_base + carry;
            output_digits[i] = static_cast<unsigned int>(cur % output_base);
            carry = cur / output_base;
        }
        while (carry > 0) {
            output_digits.insert(output_digits.begin(),
                                 static_cast<unsigned int>(carry % output_base));
            carry /= output_base;
        }
    }

    // Strip leading zeros; zero itself is represented by an empty vector.
    std::size_t first_nonzero = 0;
    while (first_nonzero < output_digits.size() && output_digits[first_nonzero] == 0) {
        ++first_nonzero;
    }
    output_digits.erase(output_digits.begin(), output_digits.begin() + static_cast<std::ptrdiff_t>(first_nonzero));
    return output_digits;
}

}  // namespace all_your_base
