import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

class ChangeCalculator {

    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        if (currencyCoins == null) {
            throw new IllegalArgumentException("Currency coins must not be null.");
        }

        List<Integer> coins = new ArrayList<>();
        for (Integer coin : currencyCoins) {
            if (coin == null || coin <= 0) {
                throw new IllegalArgumentException("Coin values must be positive.");
            }
            coins.add(coin);
        }
        Collections.sort(coins);
        this.currencyCoins = coins;
    }

    List<Integer> computeMostEfficientChange(int grandTotal) {
        if (grandTotal < 0) {
            throw new IllegalArgumentException("Negative totals are not allowed.");
        }
        if (grandTotal == 0) {
            return new ArrayList<>();
        }

        int[] minCoins = new int[grandTotal + 1];
        Arrays.fill(minCoins, Integer.MAX_VALUE);
        minCoins[0] = 0;

        for (int total = 1; total <= grandTotal; total++) {
            for (int coin : currencyCoins) {
                if (coin > total) {
                    break;
                }
                int previous = minCoins[total - coin];
                if (previous != Integer.MAX_VALUE) {
                    minCoins[total] = Math.min(minCoins[total], previous + 1);
                }
            }
        }

        if (minCoins[grandTotal] == Integer.MAX_VALUE) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        List<Integer> change = new ArrayList<>(minCoins[grandTotal]);
        int remaining = grandTotal;
        while (remaining > 0) {
            for (int coin : currencyCoins) {
                if (coin > remaining) {
                    break;
                }
                int previous = minCoins[remaining - coin];
                if (previous != Integer.MAX_VALUE && previous + 1 == minCoins[remaining]) {
                    change.add(coin);
                    remaining -= coin;
                    break;
                }
            }
        }

        return change;
    }
}
