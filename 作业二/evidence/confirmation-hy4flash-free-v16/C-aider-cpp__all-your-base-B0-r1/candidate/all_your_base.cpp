#include "all_your_base.h"

#include <algorithm>
#include <cstdint>
#include <stdexcept>

namespace all_your_base {
namespace {

std::vector<unsigned int> divide_by(std::vector<unsigned int> digits,
                                    unsigned int input_base,
                                    unsigned int divisor,
                                    unsigned int &remainder) {
    std::vector<unsigned int> quotient;
    quotient.reserve(digits.size());

    std::uint64_t current_remainder = 0;
    for (unsigned int digit : digits) {
        const std::uint64_t current =
            current_remainder * static_cast<std::uint64_t>(input_base) + digit;
        quotient.push_back(static_cast<unsigned int>(current / divisor));
        current_remainder = current % divisor;
    }

    while (!quotient.empty() && quotient.front() == 0) {
        quotient.erase(quotient.begin());
    }

    remainder = static_cast<unsigned int>(current_remainder);
    return quotient;
}

}  // namespace

std::vector<unsigned int> convert(unsigned int input_base,
                                  std::vector<unsigned int> input_digits,
                                  unsigned int output_base) {
    if (input_base < 2 || output_base < 2) {
        throw std::invalid_argument("Bases must be at least 2");
    }

    for (unsigned int digit : input_digits) {
        if (digit >= input_base) {
            throw std::invalid_argument("Digit is invalid for the input base");
        }
    }

    while (!input_digits.empty() && input_digits.front() == 0) {
        input_digits.erase(input_digits.begin());
    }

    std::vector<unsigned int> output_digits;
    while (!input_digits.empty()) {
        unsigned int remainder = 0;
        input_digits = divide_by(input_digits, input_base, output_base, remainder);
        output_digits.push_back(remainder);
    }

    std::reverse(output_digits.begin(), output_digits.end());
    return output_digits;
}

}  // namespace all_your_base
