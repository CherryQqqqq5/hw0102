import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.TreeSet;

class ChangeCalculator {

    private final List<Integer> coins;

    ChangeCalculator(List<Integer> currencyCoins) {
        TreeSet<Integer> sorted = new TreeSet<>();
        for (Integer coin : currencyCoins) {
            if (coin == null || coin <= 0) {
                throw new IllegalArgumentException("Coins must be positive values.");
            }
            sorted.add(coin);
        }
        this.coins = new ArrayList<>(sorted);
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
        Arrays.fill(minCoins, unreachable);
        minCoins[0] = 0;

        for (int amount = 1; amount <= grandTotal; amount++) {
            for (int coin : coins) {
                if (coin > amount) {
                    break;
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
            change.add(lastCoin[remaining]);
            remaining -= lastCoin[remaining];
        }

        Collections.sort(change);
        return change;
    }

}
