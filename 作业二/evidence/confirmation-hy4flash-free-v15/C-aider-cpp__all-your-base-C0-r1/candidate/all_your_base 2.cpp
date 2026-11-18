#include "all_your_base.h"

#include <algorithm>
#include <stdexcept>

namespace all_your_base {

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

    auto first_nonzero = std::find_if(digits.begin(), digits.end(),
                                      [](unsigned int digit) { return digit != 0; });
    if (first_nonzero == digits.end()) {
        return {};
    }

    std::vector<unsigned int> number(first_nonzero, digits.end());
    std::vector<unsigned int> result;

    while (!number.empty()) {
        unsigned long long remainder = 0;
        std::vector<unsigned int> quotient;
        bool leading_zero = true;

        for (unsigned int digit : number) {
            const unsigned long long current = remainder * from_base + digit;
            const unsigned int quotient_digit =
                static_cast<unsigned int>(current / to_base);
            remainder = current % to_base;

            if (!leading_zero || quotient_digit != 0) {
                quotient.push_back(quotient_digit);
                leading_zero = false;
            }
        }

        result.push_back(static_cast<unsigned int>(remainder));
        number.swap(quotient);
    }

    std::reverse(result.begin(), result.end());
    return result;
}

}  // namespace all_your_base
