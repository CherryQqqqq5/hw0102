import java.util.ArrayList;
import java.util.List;

class PigLatinTranslator {

    private static final String VOWELS = "aeiou";

    public String translate(String phrase) {
        if (phrase == null) {
            return null;
        }

        List<String> words = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        for (int i = 0; i < phrase.length(); i++) {
            char c = phrase.charAt(i);
            if (Character.isWhitespace(c)) {
                if (current.length() > 0) {
                    words.add(current.toString());
                    current.setLength(0);
                }
            } else {
                current.append(c);
            }
        }
        if (current.length() > 0) {
            words.add(current.toString());
        }

        StringBuilder result = new StringBuilder();
        for (String word : words) {
            if (result.length() > 0) {
                result.append(' ');
            }
            result.append(translateWord(word));
        }
        return result.toString();
    }

    private String translateWord(String word) {
        int length = word.length();
        if (length == 0) {
            return word;
        }

        // Rule 1: begins with a vowel, or starts with "xr" or "yt".
        if (isVowel(word.charAt(0)) || word.startsWith("xr") || word.startsWith("yt")) {
            return word + "ay";
        }

        // Walk the leading consonant cluster to find where the stem starts.
        int split = 0;
        while (split < length && !isVowel(word.charAt(split))) {
            char c = word.charAt(split);
            // Rule 4: one or more consonants followed by 'y' -> move only the consonants.
            if (c == 'y' && split > 0) {
                break;
            }
            // Rule 3: zero or more consonants followed by "qu" -> move consonants and "qu".
            if (c == 'q' && split + 1 < length && word.charAt(split + 1) == 'u') {
                split += 2;
                break;
            }
            split++;
        }

        // Rules 2, 3 and 4: move the leading cluster to the end, then add "ay".
        return word.substring(split) + word.substring(0, split) + "ay";
    }

    private static boolean isVowel(char c) {
        return VOWELS.indexOf(c) >= 0;
    }
}
