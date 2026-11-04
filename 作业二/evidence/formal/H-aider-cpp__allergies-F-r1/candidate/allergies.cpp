#include "allergies.h"

#include <unordered_map>

namespace allergies {

namespace {

const std::unordered_map<std::string, unsigned int>& allergen_scores() {
    static const std::unordered_map<std::string, unsigned int> scores = {
        {"eggs", 1},
        {"peanuts", 2},
        {"shellfish", 4},
        {"strawberries", 8},
        {"tomatoes", 16},
        {"chocolate", 32},
        {"pollen", 64},
        {"cats", 128},
    };
    return scores;
}

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score) {}

bool allergy_test::is_allergic_to(const std::string& allergen) const {
    const auto& scores = allergen_scores();
    const auto it = scores.find(allergen);
    if (it == scores.end()) {
        return false;
    }
    return (score_ & it->second) != 0;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (const auto& entry : allergen_scores()) {
        if ((score_ & entry.second) != 0) {
            result.emplace(entry.first);
        }
    }
    return result;
}

}  // namespace allergies
