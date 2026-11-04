#include "parallel_letter_frequency.h"

#include <algorithm>
#include <cctype>
#include <cstddef>
#include <functional>
#include <thread>
#include <vector>

namespace parallel_letter_frequency {

namespace {

using counts_t = std::map<char, unsigned>;

void count_range(std::vector<std::string_view> const& texts,
                 std::size_t begin,
                 std::size_t end,
                 counts_t& out) {
    for (std::size_t i = begin; i < end; ++i) {
        for (char ch : texts[i]) {
            auto const uc = static_cast<unsigned char>(ch);
            if (std::isalpha(uc) != 0) {
                out[static_cast<char>(std::tolower(uc))] += 1u;
            }
        }
    }
}

}  // namespace

counts_t frequency(std::vector<std::string_view> const& texts) {
    counts_t result;
    if (texts.empty()) {
        return result;
    }

    std::size_t const hw = std::thread::hardware_concurrency();
    std::size_t threads_wanted = hw == 0 ? 1 : static_cast<std::size_t>(hw);
    std::size_t const n = std::min(threads_wanted, texts.size());

    if (n <= 1) {
        count_range(texts, 0, texts.size(), result);
        return result;
    }

    std::vector<counts_t> partial(n);
    std::vector<std::thread> workers;
    workers.reserve(n - 1);

    std::size_t const chunk = texts.size() / n;
    std::size_t const remainder = texts.size() % n;
    std::size_t begin = 0;

    for (std::size_t t = 0; t < n; ++t) {
        std::size_t const len = chunk + (t < remainder ? 1 : 0);
        std::size_t const end = begin + len;
        if (t + 1 == n) {
            count_range(texts, begin, end, partial[t]);
        } else {
            workers.emplace_back(count_range, std::cref(texts), begin, end,
                                 std::ref(partial[t]));
        }
        begin = end;
    }

    for (auto& worker : workers) {
        worker.join();
    }

    for (auto const& local : partial) {
        for (auto const& entry : local) {
            result[entry.first] += entry.second;
        }
    }
    return result;
}

}  // namespace parallel_letter_frequency
