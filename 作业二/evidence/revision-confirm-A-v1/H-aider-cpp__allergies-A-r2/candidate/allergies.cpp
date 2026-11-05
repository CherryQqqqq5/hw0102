#include "allergies.h"

namespace allergies {

namespace {

const unsigned int kAllergenScores[] = {1,   2,   4,    8,
                                        16,  32,  64,   128};
const char* const kAllergenNames[] = {"eggs",     "peanuts", "shellfish",
                                      "strawberries", "tomatoes", "chocolate",
                                      "pollen",   "cats"};

const unsigned int kAllergenCount =
    sizeof(kAllergenScores) / sizeof(kAllergenScores[0]);

}  // namespace

allergy_test::allergy_test(unsigned int score) : score_(score & 0xFFu) {}

bool allergy_test::is_allergic_to(const std::string& item) const {
    for (unsigned int i = 0; i < kAllergenCount; ++i) {
        if (item == kAllergenNames[i]) {
            return (score_ & kAllergenScores[i]) != 0;
        }
    }
    return false;
}

std::unordered_set<std::string> allergy_test::get_allergies() const {
    std::unordered_set<std::string> result;
    for (unsigned int i = 0; i < kAllergenCount; ++i) {
        if ((score_ & kAllergenScores[i]) != 0) {
            result.emplace(kAllergenNames[i]);
        }
    }
    return result;
}

}  // namespace allergies
