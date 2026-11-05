#include "allergies.h"

namespace allergies {

namespace {

struct allergen {
    unsigned int value;
    const char* name;
};

const allergen allergens[] = {
    {1, "eggs"},
    {2, "peanuts"},
    {4, "shellfish"},
    {8, "strawberries"},
    {16, "tomatoes"},
    {32, "chocolate"},
    {64, "pollen"},
    {128, "cats"},
};

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score & 0xFF) {}

bool allergy_test::is_allergic_to(const std::string& item) const {
    for (const auto& a : allergens) {
        if (item == a.name) {
            return (score_ & a.value) != 0;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (const auto& a : allergens) {
        if ((score_ & a.value) != 0) {
            result.emplace(a.name);
        }
    }
    return result;
}

}  // namespace allergies
