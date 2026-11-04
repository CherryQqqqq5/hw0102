#include "allergies.h"

namespace allergies {

allergy_test::allergy_test(unsigned int score) : score_{score & 0xFFu} {}

bool allergy_test::is_allergic_to(const std::string& item) const {
    return get_allergies().count(item) > 0;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;

    if (score_ & 1u) {
        result.emplace("eggs");
    }
    if (score_ & 2u) {
        result.emplace("peanuts");
    }
    if (score_ & 4u) {
        result.emplace("shellfish");
    }
    if (score_ & 8u) {
        result.emplace("strawberries");
    }
    if (score_ & 16u) {
        result.emplace("tomatoes");
    }
    if (score_ & 32u) {
        result.emplace("chocolate");
    }
    if (score_ & 64u) {
        result.emplace("pollen");
    }
    if (score_ & 128u) {
        result.emplace("cats");
    }

    return result;
}

}  // namespace allergies
