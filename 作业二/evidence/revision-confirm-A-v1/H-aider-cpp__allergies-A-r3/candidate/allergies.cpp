#include "allergies.h"

#include <array>
#include <utility>

namespace allergies {

namespace {

const std::array<std::pair<const char*, unsigned int>, 8> allergens = {{
    {"eggs", 1u},
    {"peanuts", 2u},
    {"shellfish", 4u},
    {"strawberries", 8u},
    {"tomatoes", 16u},
    {"chocolate", 32u},
    {"pollen", 64u},
    {"cats", 128u},
}};

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score) {}

bool allergy_test::is_allergic_to(const std::string& allergen) const {
    for (const auto& entry : allergens) {
        if (allergen == entry.first) {
            return (score_ & entry.second) != 0u;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (const auto& entry : allergens) {
        if ((score_ & entry.second) != 0u) {
            result.emplace(entry.first);
        }
    }
    return result;
}

}  // namespace allergies
