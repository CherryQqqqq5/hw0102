import java.util.Arrays;
import java.util.stream.Collectors;

class PigLatinTranslator {
    public String translate(String phrase) {
        return Arrays.stream(phrase.split(" "))
                .map(this::translateWord)
                .collect(Collectors.joining(" "));
    }

    private String translateWord(String word) {
        if (word.isEmpty()) {
            return word;
        }
        String lower = word.toLowerCase();
        if (isVowel(lower.charAt(0)) || lower.startsWith("xr") || lower.startsWith("yt")) {
            return word + "ay";
        }

        int n = lower.length();
        int i = 0;
        while (i < n && !isVowel(lower.charAt(i))) {
            char c = lower.charAt(i);
            if (c == 'q' && i + 1 < n && lower.charAt(i + 1) == 'u') {
                i += 2;
                break;
            }
            if (c == 'y' && i > 0) {
                break;
            }
            i++;
        }
        return word.substring(i) + word.substring(0, i) + "ay";
    }

    private boolean isVowel(char c) {
        return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';
    }
}
