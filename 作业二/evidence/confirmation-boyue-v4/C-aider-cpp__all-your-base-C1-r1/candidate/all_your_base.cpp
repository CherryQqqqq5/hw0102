#include "all_your_base.h"

#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(
    unsigned int input_base,
    const std::vector<unsigned int>& input_digits,
    unsigned int output_base) {
    if (input_base < 2) {
        throw std::invalid_argument("input base must be at least 2");
    }
    if (output_base < 2) {
        throw std::invalid_argument("output base must be at least 2");
    }

    for (unsigned int digit : input_digits) {
        if (digit >= input_base) {
            throw std::invalid_argument(
                "all digits must be less than the input base");
        }
    }

    // The intermediate value is built directly in output-base digits
    // (least-significant digit first). This avoids converting to a fixed-size
    // machine integer and therefore also avoids arithmetic overflow.
    std::vector<unsigned int> little_endian;

    for (unsigned int digit : input_digits) {
        unsigned long long carry = digit;

        // little_endian = little_endian * input_base + digit
        for (unsigned int& value_digit : little_endian) {
            carry += static_cast<unsigned long long>(value_digit) * input_base;
            value_digit = static_cast<unsigned int>(carry % output_base);
            carry /= output_base;
        }

        while (carry != 0) {
            little_endian.push_back(
                static_cast<unsigned int>(carry % output_base));
            carry /= output_base;
        }
    }

    // Zero is represented by an empty digit list, matching the requirements.
    return std::vector<unsigned int>(little_endian.rbegin(),
                                     little_endian.rend());
}

}  // namespace all_your_base
