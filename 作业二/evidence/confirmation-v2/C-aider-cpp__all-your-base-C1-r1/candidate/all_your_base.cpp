#include "all_your_base.h"

#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int input_base,
                                  const std::vector<unsigned int>& digits,
                                  unsigned int output_base) {
    if (input_base < 2) {
        throw std::invalid_argument("input base must be >= 2");
    }
    if (output_base < 2) {
        throw std::invalid_argument("output base must be >= 2");
    }
    for (unsigned int digit : digits) {
        if (digit >= input_base) {
            throw std::invalid_argument("digit is out of range for input base");
        }
    }

    unsigned long long value = 0;
    for (unsigned int digit : digits) {
        value = value * input_base + digit;
    }

    std::vector<unsigned int> result;
    while (value > 0) {
        result.insert(result.begin(), static_cast<unsigned int>(value % output_base));
        value /= output_base;
    }
    return result;
}

}  // namespace all_your_base
