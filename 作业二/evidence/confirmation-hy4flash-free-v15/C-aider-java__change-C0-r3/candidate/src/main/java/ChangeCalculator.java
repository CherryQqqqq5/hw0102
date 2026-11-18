import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

class ChangeCalculator {
    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        this.currencyCoins = new ArrayList<>();
        if (currencyCoins != null) {
            for (Integer coin : currencyCoins) {
                if (coin != null && coin > 0) {
                    this.currencyCoins.add(coin);
                }
            }
        }
        Collections.sort(this.currencyCoins);
    }

    List<Integer> computeMostEfficientChange(int grandTotal) {
        if (grandTotal < 0) {
            throw new IllegalArgumentException("Negative totals are not allowed.");
        }

        int[] minimumCoins = new int[grandTotal + 1];
        int[] previousCoin = new int[grandTotal + 1];
        java.util.Arrays.fill(minimumCoins, Integer.MAX_VALUE);
        minimumCoins[0] = 0;

        for (int amount = 1; amount <= grandTotal; amount++) {
            for (int coin : currencyCoins) {
                if (coin > amount || minimumCoins[amount - coin] == Integer.MAX_VALUE) {
                    continue;
                }

                int candidate = minimumCoins[amount - coin] + 1;
                if (candidate < minimumCoins[amount]) {
                    minimumCoins[amount] = candidate;
                    previousCoin[amount] = coin;
                }
            }
        }

        if (minimumCoins[grandTotal] == Integer.MAX_VALUE) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        List<Integer> change = new ArrayList<>();
        int remaining = grandTotal;
        while (remaining > 0) {
            int coin = previousCoin[remaining];
            change.add(coin);
            remaining -= coin;
        }
        Collections.sort(change);
        return change;
    }
}
