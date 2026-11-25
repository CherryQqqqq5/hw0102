#include "all_your_base.h"

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

    unsigned long long value = 0;
    for (unsigned int digit : input_digits) {
        if (digit >= input_base) {
            throw std::invalid_argument("digit is invalid for input base");
        }
        value = value * input_base + digit;
    }

    if (value == 0) {
        return {};
    }

    std::vector<unsigned int> result;
    while (value > 0) {
        result.push_back(static_cast<unsigned int>(value % output_base));
        value /= output_base;
    }

    return {result.rbegin(), result.rend()};
}

}  // namespace all_your_base
