import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

class ChangeCalculator {
    private final List<Integer> currencyCoins;

    ChangeCalculator(List<Integer> currencyCoins) {
        if (currencyCoins == null) {
            throw new IllegalArgumentException("Currency coins cannot be null.");
        }

        List<Integer> coins = new ArrayList<>();
        for (Integer coin : currencyCoins) {
            if (coin == null || coin <= 0) {
                throw new IllegalArgumentException("Coin denominations must be positive.");
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

        List<List<Integer>> bestForAmount = new ArrayList<>(grandTotal + 1);
        for (int amount = 0; amount <= grandTotal; amount++) {
            bestForAmount.add(null);
        }
        bestForAmount.set(0, new ArrayList<Integer>());

        for (int amount = 1; amount <= grandTotal; amount++) {
            List<Integer> best = null;

            for (int coin : currencyCoins) {
                if (coin > amount) {
                    break;
                }

                List<Integer> remainingCoins = bestForAmount.get(amount - coin);
                if (remainingCoins == null) {
                    continue;
                }

                List<Integer> candidate = new ArrayList<>(remainingCoins.size() + 1);
                candidate.addAll(remainingCoins);
                candidate.add(coin);

                if (best == null || candidate.size() < best.size()) {
                    best = candidate;
                }
            }

            bestForAmount.set(amount, best);
        }

        List<Integer> result = bestForAmount.get(grandTotal);
        if (result == null) {
            throw new IllegalArgumentException(
                    "The total " + grandTotal + " cannot be represented in the given currency.");
        }

        List<Integer> orderedResult = new ArrayList<>(result);
        Collections.sort(orderedResult);
        return orderedResult;
    }
}
