#include "all_your_base.h"

#include <stdexcept>

namespace all_your_base {

namespace {

// Returns true if every digit in the (input-base) representation is zero.
bool is_zero(const std::vector<unsigned int>& digits) {
    for (unsigned int digit : digits) {
        if (digit != 0) {
            return false;
        }
    }
    return true;
}

}  // namespace

std::vector<unsigned int> convert(unsigned int input_base,
                                  const std::vector<unsigned int>& digits,
                                  unsigned int output_base) {
    if (input_base < 2) {
        throw std::invalid_argument("input base must be at least 2");
    }
    if (output_base < 2) {
        throw std::invalid_argument("output base must be at least 2");
    }

    std::vector<unsigned int> work;
    work.reserve(digits.size());
    bool seen_nonzero = false;
    for (unsigned int digit : digits) {
        if (digit >= input_base) {
            throw std::invalid_argument("digit out of range for input base");
        }
        if (digit != 0) {
            seen_nonzero = true;
        }
        if (seen_nonzero) {
            work.push_back(digit);
        }
    }

    if (work.empty()) {
        return {};
    }

    // Repeated division of the input-base representation by the output base.
    // Intermediate values stay below 2^64, so unsigned long long is safe.
    std::vector<unsigned int> result;
    while (!is_zero(work)) {
        unsigned long long remainder = 0;
        for (unsigned int& digit : work) {
            unsigned long long current =
                remainder * static_cast<unsigned long long>(input_base) + digit;
            digit = static_cast<unsigned int>(current / output_base);
            remainder = current % output_base;
        }
        result.insert(result.begin(), static_cast<unsigned int>(remainder));
    }

    return result;
}

}  // namespace all_your_base
