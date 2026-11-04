#include "allergies.h"

namespace allergies {

namespace {

struct allergen {
    const char* name;
    unsigned int value;
};

const allergen allergens[] = {
    {"eggs", 1},        {"peanuts", 2},   {"shellfish", 4},
    {"strawberries", 8}, {"tomatoes", 16}, {"chocolate", 32},
    {"pollen", 64},     {"cats", 128},
};

}  // namespace

allergy_test::allergy_test(unsigned int score) {
    for (const auto& item : allergens) {
        if ((score & item.value) != 0u) {
            allergies_.emplace(item.name);
        }
    }
}

bool allergy_test::is_allergic_to(const std::string& allergen) const {
    return allergies_.count(allergen) != 0u;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    return allergies_;
}

}  // namespace allergies
