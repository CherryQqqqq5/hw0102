import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

class ChangeCalculator {

    private static final int UNREACHABLE = Integer.MAX_VALUE;

    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        List<Integer> coins = new ArrayList<>(currencyCoins);
        Collections.sort(coins);
        this.currencyCoins = coins;
    }

    List<Integer> computeMostEfficientChange(int grandTotal) {
        if (grandTotal < 0) {
            throw new IllegalArgumentException("Negative totals are not allowed.");
        }

        List<Integer> change = new ArrayList<>();
        if (grandTotal == 0) {
            return change;
        }

        // minCoins[a] = fewest coins needed to make amount a.
        int[] minCoins = new int[grandTotal + 1];
        int[] coinUsed = new int[grandTotal + 1];
        Arrays.fill(minCoins, UNREACHABLE);
        minCoins[0] = 0;

        for (int amount = 1; amount <= grandTotal; amount++) {
            for (int coin : currencyCoins) {
                if (coin <= amount
                        && minCoins[amount - coin] != UNREACHABLE
                        && minCoins[amount - coin] + 1 < minCoins[amount]) {
                    minCoins[amount] = minCoins[amount - coin] + 1;
                    coinUsed[amount] = coin;
                }
            }
        }

        if (minCoins[grandTotal] == UNREACHABLE) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        int amount = grandTotal;
        while (amount > 0) {
            int coin = coinUsed[amount];
            change.add(coin);
            amount -= coin;
        }
        Collections.sort(change);
        return change;
    }
}
