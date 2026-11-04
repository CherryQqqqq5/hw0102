#include "allergies.h"

namespace allergies {

namespace {

struct allergen_info {
    const char* name;
    unsigned int value;
};

const allergen_info allergens[] = {
    {"eggs", 1},        {"peanuts", 2},     {"shellfish", 4},
    {"strawberries", 8}, {"tomatoes", 16},   {"chocolate", 32},
    {"pollen", 64},     {"cats", 128},
};

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score) {}

bool allergy_test::is_allergic_to(const std::string& item) const {
    for (const auto& allergen : allergens) {
        if (item == allergen.name) {
            return (score_ & allergen.value) != 0;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (const auto& allergen : allergens) {
        if ((score_ & allergen.value) != 0) {
            result.emplace(allergen.name);
        }
    }
    return result;
}

}  // namespace allergies
