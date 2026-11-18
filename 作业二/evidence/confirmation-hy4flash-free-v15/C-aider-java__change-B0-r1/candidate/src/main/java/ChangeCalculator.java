import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

class ChangeCalculator {
    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        if (currencyCoins == null) {
            throw new IllegalArgumentException("Currency coins cannot be null.");
        }

        List<Integer> coins = new ArrayList<>();
        for (Integer coin : currencyCoins) {
            if (coin == null || coin <= 0) {
                throw new IllegalArgumentException("Coin values must be positive.");
            }
            if (!coins.contains(coin)) {
                coins.add(coin);
            }
        }
        Collections.sort(coins);
        this.currencyCoins = Collections.unmodifiableList(coins);
    }

    List<Integer> computeMostEfficientChange(int grandTotal) {
        if (grandTotal < 0) {
            throw new IllegalArgumentException("Negative totals are not allowed.");
        }

        List<List<Integer>> coinsUsed = new ArrayList<>(grandTotal + 1);
        coinsUsed.add(new ArrayList<>());

        for (int amount = 1; amount <= grandTotal; amount++) {
            List<Integer> bestCombination = null;

            for (int coin : currencyCoins) {
                if (coin > amount) {
                    break;
                }

                List<Integer> remainderCombination = coinsUsed.get(amount - coin);
                if (remainderCombination == null) {
                    continue;
                }

                List<Integer> combination = new ArrayList<>(remainderCombination.size() + 1);
                combination.add(coin);
                combination.addAll(remainderCombination);

                if (bestCombination == null || combination.size() < bestCombination.size()) {
                    bestCombination = combination;
                }
            }

            coinsUsed.add(bestCombination);
        }

        List<Integer> result = coinsUsed.get(grandTotal);
        if (result == null) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        return new ArrayList<>(result);
    }
}
