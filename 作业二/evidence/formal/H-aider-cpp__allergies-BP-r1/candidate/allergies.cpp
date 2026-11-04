#include "allergies.h"

#include <array>
#include <utility>

namespace allergies {

namespace {

const std::array<std::pair<unsigned int, const char *>, 8> allergens = {{
    {1, "eggs"},
    {2, "peanuts"},
    {4, "shellfish"},
    {8, "strawberries"},
    {16, "tomatoes"},
    {32, "chocolate"},
    {64, "pollen"},
    {128, "cats"},
}};

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score) {}

bool allergy_test::is_allergic_to(const std::string &item) const {
    for (const auto &allergen : allergens) {
        if (item == allergen.second) {
            return (score_ & allergen.first) != 0;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (const auto &allergen : allergens) {
        if ((score_ & allergen.first) != 0) {
            result.emplace(allergen.second);
        }
    }
    return result;
}

}  // namespace allergies
