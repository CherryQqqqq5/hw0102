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
        List<Integer> change = new ArrayList<>();
        if (grandTotal == 0) {
            return change;
        }

        final int unreachable = Integer.MAX_VALUE;
        int[] minCoins = new int[grandTotal + 1];
        int[] lastCoin = new int[grandTotal + 1];

        minCoins[0] = 0;
        for (int amount = 1; amount <= grandTotal; amount++) {
            minCoins[amount] = unreachable;
            for (int coin : currencyCoins) {
                if (coin <= 0 || coin > amount) {
                    continue;
                }
                int previous = minCoins[amount - coin];
                if (previous != unreachable && previous + 1 < minCoins[amount]) {
                    minCoins[amount] = previous + 1;
                    lastCoin[amount] = coin;
                }
            }
        }

        if (minCoins[grandTotal] == unreachable) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        int remaining = grandTotal;
        while (remaining > 0) {
            int coin = lastCoin[remaining];
            change.add(coin);
            remaining -= coin;
        }

        Collections.sort(change);
        return change;
    }
}
