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
        for (Integer coin : currencyCoins) {
            if (coin == null || coin <= 0) {
                throw new IllegalArgumentException("Currency coins must be positive.");
            }
        }
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
        int[] minimumCoins = new int[grandTotal + 1];
        int[] lastCoin = new int[grandTotal + 1];
        Arrays.fill(minimumCoins, unreachable);
        minimumCoins[0] = 0;

        for (int amount = 1; amount <= grandTotal; amount++) {
            for (int coin : currencyCoins) {
                if (coin <= amount && minimumCoins[amount - coin] != unreachable) {
                    int candidate = minimumCoins[amount - coin] + 1;
                    if (candidate < minimumCoins[amount]) {
                        minimumCoins[amount] = candidate;
                        lastCoin[amount] = coin;
                    }
                }
            }
        }

        if (minimumCoins[grandTotal] == unreachable) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        for (int amount = grandTotal; amount > 0; amount -= lastCoin[amount]) {
            change.add(lastCoin[amount]);
        }
        Collections.sort(change);
        return change;
    }
}
