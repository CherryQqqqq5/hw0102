import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

class ChangeCalculator {
    private static final int UNREACHABLE = Integer.MAX_VALUE / 4;

    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        if (currencyCoins == null) {
            throw new IllegalArgumentException("Currency coins cannot be null.");
        }

        List<Integer> coins = new ArrayList<>();
        for (Integer coin : currencyCoins) {
            if (coin == null || coin <= 0) {
                throw new IllegalArgumentException("Currency coins must be positive.");
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

        int[] fewestCoins = new int[grandTotal + 1];
        int[] lastCoin = new int[grandTotal + 1];
        Arrays.fill(fewestCoins, 1, fewestCoins.length, UNREACHABLE);

        for (int amount = 1; amount <= grandTotal; amount++) {
            for (int coin : currencyCoins) {
                if (coin > amount) {
                    break;
                }

                int remaining = amount - coin;
                if (fewestCoins[remaining] == UNREACHABLE) {
                    continue;
                }

                int candidateCount = fewestCoins[remaining] + 1;
                if (candidateCount < fewestCoins[amount]) {
                    fewestCoins[amount] = candidateCount;
                    lastCoin[amount] = coin;
                }
            }
        }

        if (fewestCoins[grandTotal] == UNREACHABLE) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        List<Integer> change = new ArrayList<>();
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
