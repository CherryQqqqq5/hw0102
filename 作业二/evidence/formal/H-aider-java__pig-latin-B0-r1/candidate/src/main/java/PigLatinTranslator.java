import java.util.Arrays;
import java.util.stream.Collectors;

class PigLatinTranslator {

    public String translate(String phrase) {
        return Arrays.stream(phrase.split(" "))
                .map(this::translateWord)
                .collect(Collectors.joining(" "));
    }

    private String translateWord(String word) {
        if (startsWithVowelSound(word)) {
            return word + "ay";
        }

        int split = consonantClusterLength(word);
        return word.substring(split) + word.substring(0, split) + "ay";
    }

    private boolean startsWithVowelSound(String word) {
        char first = word.charAt(0);
        if (first == 'a' || first == 'e' || first == 'i' || first == 'o' || first == 'u') {
            return true;
        }
        return word.startsWith("xr") || word.startsWith("yt");
    }

    private int consonantClusterLength(String word) {
        int i = 0;
        while (i < word.length()) {
            char c = word.charAt(i);
            if (isVowel(c)) {
                break;
            }
            if (c == 'q' && i + 1 < word.length() && word.charAt(i + 1) == 'u') {
                return i + 2;
            }
            if (c == 'y' && i > 0) {
                return i;
            }
            i++;
        }
        return i;
    }

    private boolean isVowel(char c) {
        return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';
    }
}
