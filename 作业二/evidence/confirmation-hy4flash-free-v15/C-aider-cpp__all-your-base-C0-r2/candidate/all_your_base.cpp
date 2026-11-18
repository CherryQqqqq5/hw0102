#include "all_your_base.h"

#include <algorithm>
#include <stdexcept>

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

    // The result is stored least-significant digit first while converting.
    std::vector<unsigned int> result;
    for (std::size_t i = first_nonzero; i < input_digits.size(); ++i) {
        unsigned long long carry = input_digits[i];

        for (std::size_t j = 0; j < result.size(); ++j) {
            unsigned long long value =
                static_cast<unsigned long long>(result[j]) * input_base + carry;
            result[j] = static_cast<unsigned int>(value % output_base);
            carry = value / output_base;
        }

        while (carry > 0) {
            result.push_back(static_cast<unsigned int>(carry % output_base));
            carry /= output_base;
        }
    }

    std::reverse(result.begin(), result.end());
    return result;
}

}  // namespace all_your_base
