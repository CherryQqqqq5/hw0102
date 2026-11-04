#include "allergies.h"

#include <array>
#include <utility>

namespace allergies {

namespace {

const std::array<std::pair<unsigned int, const char *>, 8> &allergen_table() {
    static const std::array<std::pair<unsigned int, const char *>, 8> table = {{
        {1, "eggs"},
        {2, "peanuts"},
        {4, "shellfish"},
        {8, "strawberries"},
        {16, "tomatoes"},
        {32, "chocolate"},
        {64, "pollen"},
        {128, "cats"},
    }};
    return table;
}

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score & 0xFFu) {}

bool allergy_test::is_allergic_to(const std::string &item) const {
    for (const auto &entry : allergen_table()) {
        if (item == entry.second) {
            return (score_ & entry.first) != 0;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (const auto &entry : allergen_table()) {
        if ((score_ & entry.first) != 0) {
            result.emplace(entry.second);
        }
    }
    return result;
}

}  // namespace allergies
