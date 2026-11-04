#include "allergies.h"

#include <utility>

namespace allergies {

namespace {

const std::pair<unsigned int, const char*> allergens[] = {
    {1u, "eggs"},         {2u, "peanuts"},    {4u, "shellfish"},
    {8u, "strawberries"}, {16u, "tomatoes"},  {32u, "chocolate"},
    {64u, "pollen"},      {128u, "cats"},
};

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score) {}

bool allergy_test::is_allergic_to(const std::string& item) const {
    for (const auto& allergen : allergens) {
        if (item == allergen.second) {
            return (score_ & allergen.first) != 0;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (const auto& allergen : allergens) {
        if ((score_ & allergen.first) != 0) {
            result.emplace(allergen.second);
        }
    }
    return result;
}

}  // namespace allergies
