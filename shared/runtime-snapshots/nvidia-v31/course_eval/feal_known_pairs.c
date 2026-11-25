#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define SEEDS (1u << 20)
#define MAX_PAIRS 64

typedef struct { uint64_t plaintext, ciphertext; } Pair;
typedef struct { uint32_t expanded, seed; } KeyEntry;
static Pair pairs[MAX_PAIRS];
static size_t pair_count;

static uint32_t expand(uint32_t seed) {
    return seed ^ (seed << 16) ^ (seed * 12345u);
}

static uint8_t rotate2(uint8_t value) {
    return (uint8_t)((value << 2) | (value >> 6));
}

static uint8_t undo_rotate2(uint8_t value) {
    return (uint8_t)((value >> 2) | (value << 6));
}

uint32_t feal_round(uint32_t value) {
    uint8_t x0 = value, x1 = value >> 8, x2 = value >> 16, x3 = value >> 24;
    uint8_t y2 = rotate2((uint8_t)((x3 ^ x2) + (x1 ^ x0) + 1));
    uint8_t y3 = rotate2((uint8_t)(x3 + y2));
    uint8_t y1 = rotate2((uint8_t)((x1 ^ x0) + y2));
    uint8_t y0 = rotate2((uint8_t)(x0 + y1 + 1));
    return (uint32_t)y0 | ((uint32_t)y1 << 8) | ((uint32_t)y2 << 16) | ((uint32_t)y3 << 24);
}

uint32_t feal_round_inverse(uint32_t value) {
    uint8_t y0 = value, y1 = value >> 8, y2 = value >> 16, y3 = value >> 24;
    uint8_t x0 = (uint8_t)(undo_rotate2(y0) - y1 - 1);
    uint8_t x3 = (uint8_t)(undo_rotate2(y3) - y2);
    uint8_t first = (uint8_t)(undo_rotate2(y1) - y2);
    uint8_t second = (uint8_t)(undo_rotate2(y2) - first - 1);
    uint8_t x1 = first ^ x0, x2 = second ^ x3;
    return (uint32_t)x0 | ((uint32_t)x1 << 8) | ((uint32_t)x2 << 16) | ((uint32_t)x3 << 24);
}

static unsigned parity_lsb(uint32_t value) {
    return (value ^ (value >> 8) ^ (value >> 16) ^ (value >> 24)) & 1u;
}

static unsigned bit18(uint32_t value) {
    return (value >> 18) & 1u;
}

static uint64_t encrypt(uint64_t plaintext, const uint32_t keys[4]) {
    uint32_t left = plaintext >> 32, right = (uint32_t)plaintext ^ left;
    for (int index = 0; index < 4; index++) {
        uint32_t next = left ^ feal_round(right ^ keys[index]);
        left = right;
        right = next;
    }
    return ((uint64_t)right << 32) | (left ^ right);
}

static int compare_keys(const void *left, const void *right) {
    uint32_t a = ((const KeyEntry *)left)->expanded, b = ((const KeyEntry *)right)->expanded;
    return (a > b) - (a < b);
}

static int seed_for(const KeyEntry *table, uint32_t expanded, uint32_t *seed) {
    size_t low = 0, high = SEEDS;
    while (low < high) {
        size_t middle = low + (high - low) / 2;
        if (table[middle].expanded < expanded) low = middle + 1;
        else high = middle;
    }
    if (low == SEEDS || table[low].expanded != expanded) return 0;
    *seed = table[low].seed;
    return 1;
}

static int consistent_outer(uint32_t key, int last_round) {
    int first = -1;
    for (size_t index = 0; index < pair_count; index++) {
        uint32_t pl = pairs[index].plaintext >> 32, pr = pairs[index].plaintext;
        uint32_t cl = pairs[index].ciphertext >> 32, cr = pairs[index].ciphertext;
        uint32_t a0 = pl ^ pr, a3 = cl ^ cr, a4 = cl;
        /* 公开轮函数恒等式：bit18(F(x)) = 各字节最低位异或值 ^ 1。 */
        unsigned value = last_round
            ? parity_lsb(a4 ^ feal_round(a3 ^ key)) ^ bit18(a3) ^ bit18(pl) ^ parity_lsb(a0)
            : parity_lsb(pl ^ feal_round(a0 ^ key)) ^ bit18(a0) ^ bit18(a4) ^ parity_lsb(a3);
        if (first < 0) first = (int)value;
        else if ((unsigned)first != value) return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <decimal-plaintext-ciphertext-pairs.txt>\n", argv[0]);
        return 2;
    }
    FILE *file = fopen(argv[1], "r");
    if (!file) { perror(argv[1]); return 2; }
    char line[256], extra;
    while (fgets(line, sizeof line, file)) {
        uint64_t plaintext, ciphertext;
        if (pair_count == MAX_PAIRS || sscanf(line, " %" SCNu64 " %" SCNu64 " %c", &plaintext, &ciphertext, &extra) != 2) {
            fprintf(stderr, "Expected16..64 well-formed decimal pairs\n");
            fclose(file);
            return 2;
        }
        for (size_t index = 0; index < pair_count; index++) {
            if (pairs[index].plaintext == plaintext) {
                fprintf(stderr, "Duplicate plaintext does not supply independent known-pair evidence\n");
                fclose(file);
                return 2;
            }
        }
        pairs[pair_count++] = (Pair){plaintext, ciphertext};
    }
    if (ferror(file)) { fclose(file); return 2; }
    fclose(file);
    if (pair_count < 16) { fprintf(stderr, "At least16 distinct known plaintexts are required\n"); return 2; }
    KeyEntry *table = malloc(SEEDS * sizeof(*table));
    uint32_t *first = malloc(SEEDS * sizeof(*first)), *last = malloc(SEEDS * sizeof(*last));
    if (!table || !first || !last) { free(table); free(first); free(last); return 2; }
    size_t n_first = 0, n_last = 0;
    for (uint32_t seed = 0; seed < SEEDS; seed++) {
        uint32_t key = expand(seed);
        table[seed] = (KeyEntry){key, seed};
        if (consistent_outer(key, 0)) first[n_first++] = seed;
        if (consistent_outer(key, 1)) last[n_last++] = seed;
    }
    qsort(table, SEEDS, sizeof(*table), compare_keys);
    fprintf(stderr, "outer_candidates=%zu,%zu known_pairs=%zu\n", n_first, n_last, pair_count);
    if (n_first && n_last > 4096 / n_first) {
        fprintf(stderr, "Insufficient discrimination; more known-pair evidence is required\n");
        free(table); free(first); free(last); return 3;
    }
    int found = 0;
    for (size_t a = 0; a < n_first && !found; a++) for (size_t d = 0; d < n_last && !found; d++) {
        uint32_t keys[4] = {expand(first[a]), 0, 0, expand(last[d])};
        uint32_t pl = pairs[0].plaintext >> 32, a0 = (uint32_t)pairs[0].plaintext ^ pl;
        uint32_t a3 = (uint32_t)(pairs[0].ciphertext >> 32) ^ (uint32_t)pairs[0].ciphertext;
        uint32_t a1 = pl ^ feal_round(a0 ^ keys[0]);
        uint32_t a2 = (uint32_t)(pairs[0].ciphertext >> 32) ^ feal_round(a3 ^ keys[3]);
        keys[1] = feal_round_inverse(a2 ^ a0) ^ a1;
        keys[2] = feal_round_inverse(a3 ^ a1) ^ a2;
        uint32_t seeds[4] = {first[a], 0, 0, last[d]};
        if (!seed_for(table, keys[1], seeds + 1) || !seed_for(table, keys[2], seeds + 2)) continue;
        int valid = 1;
        for (size_t index = 0; index < pair_count; index++) {
            if (encrypt(pairs[index].plaintext, keys) != pairs[index].ciphertext) { valid = 0; break; }
        }
        if (valid) {
            printf("{\"seed_bits\":20,\"seeds\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],\"verified_known_pairs\":%zu}\n",
                seeds[0], seeds[1], seeds[2], seeds[3], pair_count);
            found = 1;
        }
    }
    free(table); free(first); free(last);
    if (!found) fprintf(stderr, "No key consistent with all supplied known pairs\n");
    return found ? 0 : 1;
}
