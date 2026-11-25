import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

class ChangeCalculator {

    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        this.currencyCoins = new ArrayList<>(currencyCoins);
    }

    List<Integer> computeMostEfficientChange(int grandTotal) {
        if (grandTotal < 0) {
            throw new IllegalArgumentException("Negative totals are not allowed.");
        }
        if (grandTotal == 0) {
            return new ArrayList<>();
        }

        List<List<Integer>> best = new ArrayList<>(grandTotal + 1);
        best.add(new ArrayList<>());
        for (int i = 1; i <= grandTotal; i++) {
            best.add(null);
        }

        for (int total = 1; total <= grandTotal; total++) {
            List<Integer> bestForTotal = null;
            for (int coin : currencyCoins) {
                if (coin <= 0 || coin > total) {
                    continue;
                }
                List<Integer> previous = best.get(total - coin);
                if (previous == null) {
                    continue;
                }
                List<Integer> candidate = new ArrayList<>(previous);
                candidate.add(coin);
                if (bestForTotal == null || candidate.size() < bestForTotal.size()) {
                    Collections.sort(candidate);
                    bestForTotal = candidate;
                }
            }
            best.set(total, bestForTotal);
        }

        List<Integer> result = best.get(grandTotal);
        if (result == null) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }
        return result;
    }

}
