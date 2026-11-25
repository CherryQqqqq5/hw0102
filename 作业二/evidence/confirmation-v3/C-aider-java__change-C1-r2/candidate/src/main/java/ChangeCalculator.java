import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

class ChangeCalculator {

    private final List<Integer> coins;

    ChangeCalculator(List<Integer> currencyCoins) {
        if (currencyCoins == null || currencyCoins.isEmpty()) {
            throw new IllegalArgumentException("Currency must contain at least one coin.");
        }
        List<Integer> cleaned = new ArrayList<>();
        for (Integer coin : currencyCoins) {
            if (coin == null || coin <= 0) {
                throw new IllegalArgumentException("Coin values must be positive.");
            }
            cleaned.add(coin);
        }
        Collections.sort(cleaned);
        this.coins = Collections.unmodifiableList(cleaned);
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
                int rest = amount - coin;
                if (minCoins[rest] != unreachable && minCoins[rest] + 1 < minCoins[amount]) {
                    minCoins[amount] = minCoins[rest] + 1;
                    lastCoin[amount] = coin;
                }
            }
        }

        if (minCoins[grandTotal] == unreachable) {
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
