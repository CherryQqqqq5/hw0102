#include "parallel_letter_frequency.h"

#include <array>
#include <cstddef>
#include <algorithm>
#include <thread>

namespace parallel_letter_frequency {

namespace {

using counts_t = std::array<std::size_t, 26>;

void count_range(std::vector<std::string_view> const& texts,
                 std::size_t begin,
                 std::size_t end,
                 counts_t& counts) {
    for (std::size_t i = begin; i < end; ++i) {
        for (char const c : texts[i]) {
            char lower = c;
            if (c >= 'A' && c <= 'Z') {
                lower = static_cast<char>(c - 'A' + 'a');
            }
            if (lower >= 'a' && lower <= 'z') {
                ++counts[static_cast<std::size_t>(lower - 'a')];
            }
        }
    }
}

}  // namespace

std::map<char, int> frequency(std::vector<std::string_view> const& texts) {
    std::map<char, int> result;
    if (texts.empty()) {
        return result;
    }

    unsigned int const hardware = std::thread::hardware_concurrency();
    std::size_t const max_threads = hardware == 0 ? 1 : hardware;
    std::size_t const thread_count =
        texts.size() < max_threads ? texts.size() : max_threads;

    std::vector<counts_t> partial(thread_count, counts_t{});
    std::vector<std::thread> workers;
    workers.reserve(thread_count > 1 ? thread_count - 1 : 0);

    std::size_t const chunk = (texts.size() + thread_count - 1) / thread_count;

    for (std::size_t t = 0; t < thread_count; ++t) {
        std::size_t const begin = t * chunk;
        std::size_t const end = std::min(begin + chunk, texts.size());
        if (begin >= end) {
            continue;
        }
        if (t == 0) {
            // Run the first chunk on the calling thread.
            count_range(texts, begin, end, partial[t]);
        } else {
            workers.emplace_back([&texts, begin, end, &counts = partial[t]]() {
                count_range(texts, begin, end, counts);
            });
        }
    }

    for (auto& worker : workers) {
        worker.join();
    }

    counts_t total{};
    for (auto const& counts : partial) {
        for (std::size_t i = 0; i < total.size(); ++i) {
            total[i] += counts[i];
        }
    }

    for (std::size_t i = 0; i < total.size(); ++i) {
        if (total[i] != 0) {
            result[static_cast<char>('a' + static_cast<int>(i))] =
                static_cast<int>(total[i]);
        }
    }

    return result;
}

}  // namespace parallel_letter_frequency
