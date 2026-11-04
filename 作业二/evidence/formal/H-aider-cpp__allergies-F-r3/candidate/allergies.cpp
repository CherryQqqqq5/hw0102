#include "allergies.h"

namespace allergies {

namespace {

struct allergen {
    const char* name;
    unsigned int value;
};

constexpr allergen allergens[] = {
    {"eggs", 1u},
    {"peanuts", 2u},
    {"shellfish", 4u},
    {"strawberries", 8u},
    {"tomatoes", 16u},
    {"chocolate", 32u},
    {"pollen", 64u},
    {"cats", 128u},
};

unsigned int value_of(const std::string& item) {
    for (const auto& a : allergens) {
        if (item == a.name) {
            return a.value;
        }
    }
    return 0u;
}

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score) {}

bool allergy_test::is_allergic_to(const std::string& item) const {
    const unsigned int value = value_of(item);
    return value != 0u && (score_ & value) != 0u;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (const auto& a : allergens) {
        if ((score_ & a.value) != 0u) {
            result.emplace(a.name);
        }
    }
    return result;
}

}  // namespace allergies
