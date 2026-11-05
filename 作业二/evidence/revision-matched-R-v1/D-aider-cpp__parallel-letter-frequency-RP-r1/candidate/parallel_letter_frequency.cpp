#include "parallel_letter_frequency.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <numeric>
#include <thread>

namespace parallel_letter_frequency {

namespace {

using counts_t = std::array<std::size_t, 26>;

counts_t count_text(std::string_view text) {
    counts_t counts{};
    for (unsigned char ch : text) {
        if (std::isalpha(ch)) {
            auto const lower = static_cast<unsigned char>(std::tolower(ch));
            ++counts[static_cast<std::size_t>(lower - 'a')];
        }
    }
    return counts;
}

void add_counts(counts_t& lhs, counts_t const& rhs) {
    for (std::size_t i = 0; i < lhs.size(); ++i) {
        lhs[i] += rhs[i];
    }
}

}  // namespace

frequency_map frequency(std::vector<std::string_view> const& texts) {
    auto const n = texts.size();
    if (n == 0) {
        return {};
    }

    auto const hw = std::thread::hardware_concurrency();
    std::size_t const worker_count =
        std::max<std::size_t>(1, std::min<std::size_t>(n, hw == 0 ? 4 : hw));

    std::vector<counts_t> partials(worker_count);
    std::vector<std::thread> workers;
    workers.reserve(worker_count);

    auto const chunk = (n + worker_count - 1) / worker_count;
    for (std::size_t w = 0; w < worker_count; ++w) {
        auto const begin = w * chunk;
        auto const end = std::min(n, begin + chunk);
        if (begin >= end) {
            continue;
        }
        partials[w] = counts_t{};
        workers.emplace_back([&texts, &partials, w, begin, end]() {
            counts_t local{};
            for (auto i = begin; i < end; ++i) {
                add_counts(local, count_text(texts[i]));
            }
            partials[w] = local;
        });
    }

    for (auto& t : workers) {
        t.join();
    }

    counts_t total{};
    for (auto const& p : partials) {
        add_counts(total, p);
    }

    frequency_map result;
    for (std::size_t i = 0; i < total.size(); ++i) {
        if (total[i] > 0) {
            result[static_cast<char>('a' + static_cast<int>(i))] = total[i];
        }
    }
    return result;
}

}
