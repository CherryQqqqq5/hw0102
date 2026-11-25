#include "all_your_base.h"

#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(int input_base,
                                  const std::vector<unsigned int>& digits,
                                  int output_base) {
    if (input_base < 2) {
        throw std::invalid_argument("input base must be at least 2");
    }
    if (output_base < 2) {
        throw std::invalid_argument("output base must be at least 2");
    }

    unsigned long long value = 0;
    for (unsigned int digit : digits) {
        if (digit >= static_cast<unsigned int>(input_base)) {
            throw std::invalid_argument("digit is not valid for the input base");
        }
        value = value * static_cast<unsigned long long>(input_base) + digit;
    }

    if (value == 0) {
        return {};
    }

    std::vector<unsigned int> result;
    while (value > 0) {
        result.insert(result.begin(),
                      static_cast<unsigned int>(
                          value % static_cast<unsigned long long>(output_base)));
        value /= static_cast<unsigned long long>(output_base);
    }
    return result;
}

}  // namespace all_your_base
