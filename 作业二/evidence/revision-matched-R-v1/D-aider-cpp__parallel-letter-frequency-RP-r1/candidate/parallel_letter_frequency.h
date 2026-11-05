#if !defined(PARALLEL_LETTER_FREQUENCY_H)
#define PARALLEL_LETTER_FREQUENCY_H

#include <cstddef>
#include <map>
#include <string_view>
#include <vector>

namespace parallel_letter_frequency {

using frequency_map = std::map<char, std::size_t>;

frequency_map frequency(std::vector<std::string_view> const& texts);

}

#endif
