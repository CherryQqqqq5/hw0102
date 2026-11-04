#include "allergies.h"

#include <array>
#include <utility>

namespace allergies {

namespace {

using allergy_pair = std::pair<unsigned int, char const*>;

constexpr std::array<allergy_pair, 8> allergen_list{{
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

allergy_test::allergy_test(unsigned int score) : score_{score} {}

bool allergy_test::is_allergic_to(std::string const& item) const {
    for (auto const& entry : allergen_list) {
        if (item == entry.second) {
            return (score_ & entry.first) != 0;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (auto const& entry : allergen_list) {
        if ((score_ & entry.first) != 0) {
            result.emplace(entry.second);
        }
    }
    return result;
}

}  // namespace allergies
