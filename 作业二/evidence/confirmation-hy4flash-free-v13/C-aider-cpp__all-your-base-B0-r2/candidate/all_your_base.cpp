#include "all_your_base.h"

#include <algorithm>
#include <stdexcept>

namespace all_your_base {
namespace {

void trim_leading_zeros(std::vector<unsigned int>& digits) {
    auto first_nonzero = digits.begin();
    while (first_nonzero != digits.end() && *first_nonzero == 0) {
        ++first_nonzero;
    }
    digits.erase(digits.begin(), first_nonzero);
}

}  // namespace

std::vector<unsigned int> convert(unsigned int from_base,
                                  const std::vector<unsigned int>& digits,
                                  unsigned int to_base) {
    if (from_base < 2 || to_base < 2) {
        throw std::invalid_argument("bases must be at least 2");
    }

    for (unsigned int digit : digits) {
        if (digit >= from_base) {
            throw std::invalid_argument("digit out of range for input base");
        }
    }

    std::vector<unsigned int> number = digits;
    trim_leading_zeros(number);

    std::vector<unsigned int> result;
    while (!number.empty()) {
        std::vector<unsigned int> quotient;
        quotient.reserve(number.size());

        unsigned long long remainder = 0;
        for (unsigned int digit : number) {
            const unsigned long long current =
                remainder * static_cast<unsigned long long>(from_base) + digit;
            quotient.push_back(static_cast<unsigned int>(current / to_base));
            remainder = current % to_base;
        }

        result.push_back(static_cast<unsigned int>(remainder));
        trim_leading_zeros(quotient);
        number.swap(quotient);
    }

    std::reverse(result.begin(), result.end());
    return result;
}

}  // namespace all_your_base
