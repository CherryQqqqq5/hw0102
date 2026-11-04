#include "allergies.h"

namespace allergies {

namespace {

struct Allergen {
    unsigned int value;
    const char* name;
};

const Allergen allergen_list[] = {
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

allergy_test::allergy_test(unsigned int score) : score_(score) {}

bool allergy_test::is_allergic_to(const std::string& item) const {
    for (const auto& allergen : allergen_list) {
        if (item == allergen.name) {
            return (score_ & allergen.value) != 0;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> allergies;
    for (const auto& allergen : allergen_list) {
        if ((score_ & allergen.value) != 0) {
            allergies.emplace(allergen.name);
        }
    }
    return allergies;
}

}  // namespace allergies
