#include "parallel_letter_frequency.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstddef>
#include <system_error>
#include <thread>
#include <vector>

namespace parallel_letter_frequency {

namespace {

std::size_t const alphabet_size = 26;

using letter_counts = std::array<int, alphabet_size>;

letter_counts count_chunk(std::vector<std::string_view> const& texts,
                         std::size_t begin, std::size_t end) {
    letter_counts counts{};
    for (std::size_t i = begin; i < end; ++i) {
        for (char const raw : texts[i]) {
            auto const c = static_cast<unsigned char>(raw);
            if (std::isalpha(c) == 0) {
                continue;
            }
            auto const lower = static_cast<unsigned char>(std::tolower(c));
            ++counts[static_cast<std::size_t>(lower - static_cast<unsigned char>('a'))];
        }
    }
    return counts;
}

}  // namespace

std::map<char, int> frequency(std::vector<std::string_view> const& texts) {
    std::map<char, int> result{};
    if (texts.empty()) {
        return result;
    }

    auto const hardware = static_cast<std::size_t>(std::thread::hardware_concurrency());
    std::size_t worker_count = std::max<std::size_t>(hardware, 1);
    worker_count = std::min(worker_count, texts.size());

    std::vector<letter_counts> partial(worker_count);
    std::vector<std::thread> threads;
    threads.reserve(worker_count);
    std::size_t started = 0;

    auto const chunk = (texts.size() + worker_count - 1) / worker_count;
    try {
        for (std::size_t w = 0; w < worker_count; ++w) {
            auto const begin = w * chunk;
            auto const end = std::min(begin + chunk, texts.size());
            threads.emplace_back([&texts, &partial, begin, end, w]() {
                partial[w] = count_chunk(texts, begin, end);
            });
            ++started;
        }
    } catch (std::system_error const&) {
        // Could not spawn every thread: handle the rest sequentially below.
    }

    for (auto& thread : threads) {
        thread.join();
    }

    for (std::size_t w = started; w < worker_count; ++w) {
        auto const begin = w * chunk;
        auto const end = std::min(begin + chunk, texts.size());
        partial[w] = count_chunk(texts, begin, end);
    }

    for (std::size_t i = 0; i < alphabet_size; ++i) {
        int total = 0;
        for (auto const& counts : partial) {
            total += counts[i];
        }
        if (total > 0) {
            result[static_cast<char>('a' + static_cast<int>(i))] = total;
        }
    }

    return result;
}

}  // namespace parallel_letter_frequency
