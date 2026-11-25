import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.TreeSet;

class ChangeCalculator {

    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        this.currencyCoins = new ArrayList<>(new TreeSet<>(currencyCoins));
    }

    List<Integer> computeMostEfficientChange(int grandTotal) {
        if (grandTotal < 0) {
            throw new IllegalArgumentException("Negative totals are not allowed.");
        }

        List<Integer> change = new ArrayList<>();
        if (grandTotal == 0) {
            return change;
        }

        int[] fewestCoins = new int[grandTotal + 1];
        int[] coinUsed = new int[grandTotal + 1];
        Arrays.fill(fewestCoins, Integer.MAX_VALUE);
        fewestCoins[0] = 0;

        for (int amount = 1; amount <= grandTotal; amount++) {
            for (int coin : currencyCoins) {
                if (coin <= 0 || coin > amount) {
                    continue;
                }
                int remainder = amount - coin;
                if (fewestCoins[remainder] != Integer.MAX_VALUE
                        && fewestCoins[remainder] + 1 < fewestCoins[amount]) {
                    fewestCoins[amount] = fewestCoins[remainder] + 1;
                    coinUsed[amount] = coin;
                }
            }
        }

        if (fewestCoins[grandTotal] == Integer.MAX_VALUE) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        for (int amount = grandTotal; amount > 0; amount -= coinUsed[amount]) {
            change.add(coinUsed[amount]);
        }
        Collections.sort(change);
        return change;
    }
}
