import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.TreeSet;

class ChangeCalculator {

    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        TreeSet<Integer> unique = new TreeSet<>();
        if (currencyCoins != null) {
            for (Integer coin : currencyCoins) {
                if (coin != null && coin > 0) {
                    unique.add(coin);
                }
            }
        }
        this.currencyCoins = new ArrayList<>(unique);
    }

    List<Integer> computeMostEfficientChange(int grandTotal) {
        if (grandTotal < 0) {
            throw new IllegalArgumentException("Negative totals are not allowed.");
        }

        List<Integer> change = new ArrayList<>();
        if (grandTotal == 0) {
            return change;
        }

        int[] minCoins = new int[grandTotal + 1];
        int[] lastCoin = new int[grandTotal + 1];
        Arrays.fill(minCoins, Integer.MAX_VALUE);
        minCoins[0] = 0;

        for (int total = 1; total <= grandTotal; total++) {
            for (int coin : currencyCoins) {
                if (coin > total) {
                    break;
                }
                int previous = minCoins[total - coin];
                if (previous != Integer.MAX_VALUE && previous + 1 < minCoins[total]) {
                    minCoins[total] = previous + 1;
                    lastCoin[total] = coin;
                }
            }
        }

        if (minCoins[grandTotal] == Integer.MAX_VALUE) {
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
