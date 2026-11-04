#if !defined(PARALLEL_LETTER_FREQUENCY_H)
#define PARALLEL_LETTER_FREQUENCY_H

#include <map>
#include <string_view>
#include <vector>

namespace parallel_letter_frequency {

std::map<char, unsigned> frequency(
    std::vector<std::string_view> const& texts);

}  // namespace parallel_letter_frequency

#endif
