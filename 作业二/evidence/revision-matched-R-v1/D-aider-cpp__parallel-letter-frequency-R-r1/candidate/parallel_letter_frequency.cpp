#include "parallel_letter_frequency.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <functional>
#include <thread>

namespace parallel_letter_frequency {

namespace {

constexpr std::size_t alphabet_size = 26;

using counts_t = std::array<std::size_t, alphabet_size>;

void count_range(const std::vector<std::string_view>& texts, std::size_t begin,
                 std::size_t end, counts_t& counts) {
    for (std::size_t i = begin; i < end; ++i) {
        for (char c : texts[i]) {
            const unsigned char u = static_cast<unsigned char>(c);
            if (u >= static_cast<unsigned char>('a') &&
                u <= static_cast<unsigned char>('z')) {
                ++counts[static_cast<std::size_t>(u - 'a')];
            } else if (u >= static_cast<unsigned char>('A') &&
                       u <= static_cast<unsigned char>('Z')) {
                ++counts[static_cast<std::size_t>(u - 'A')];
            }
        }
    }
}

}  // namespace

std::map<char, int> frequency(const std::vector<std::string_view>& texts) {
    std::map<char, int> result;
    if (texts.empty()) {
        return result;
    }

    const std::size_t hardware = std::thread::hardware_concurrency();
    const std::size_t available = hardware == 0 ? 1 : hardware;
    const std::size_t num_threads =
        std::max<std::size_t>(1, std::min<std::size_t>(texts.size(), available));

    std::vector<counts_t> partial(num_threads);
    std::vector<std::thread> workers;
    workers.reserve(num_threads);

    const std::size_t chunk = texts.size() / num_threads;
    const std::size_t remainder = texts.size() % num_threads;
    std::size_t begin = 0;
    for (std::size_t t = 0; t < num_threads; ++t) {
        const std::size_t len = chunk + (t < remainder ? 1 : 0);
        const std::size_t end = begin + len;
        partial[t].fill(0);
        workers.emplace_back(count_range, std::cref(texts), begin, end,
                             std::ref(partial[t]));
        begin = end;
    }

    for (std::thread& worker : workers) {
        worker.join();
    }

    for (const counts_t& counts : partial) {
        for (std::size_t i = 0; i < alphabet_size; ++i) {
            if (counts[i] != 0) {
                result[static_cast<char>('a' + static_cast<int>(i))] +=
                    static_cast<int>(counts[i]);
            }
        }
    }

    return result;
}

}  // namespace parallel_letter_frequency
