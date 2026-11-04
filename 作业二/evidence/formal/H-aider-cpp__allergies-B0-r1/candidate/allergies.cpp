#include "allergies.h"

#include <array>
#include <utility>

namespace allergies {

namespace {

constexpr std::array<std::pair<unsigned int, const char*>, 8> allergen_scores{{
    {1u, "eggs"},
    {2u, "peanuts"},
    {4u, "shellfish"},
    {8u, "strawberries"},
    {16u, "tomatoes"},
    {32u, "chocolate"},
    {64u, "pollen"},
    {128u, "cats"},
}};

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score) {
    for (const auto& entry : allergen_scores) {
        if ((score_ & entry.first) != 0u) {
            allergies_.emplace(entry.second);
        }
    }
}

bool allergy_test::is_allergic_to(const std::string& item) const {
    return allergies_.find(item) != allergies_.end();
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    return allergies_;
}

}  // namespace allergies
