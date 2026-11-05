import java.util.Set;

class PigLatinTranslator {
    private static final Set<Character> VOWELS = Set.of('a', 'e', 'i', 'o', 'u');

    public String translate(String phrase) {
        StringBuilder result = new StringBuilder();
        String[] words = phrase.trim().split("\\s+");
        for (int k = 0; k < words.length; k++) {
            if (k > 0) {
                result.append(' ');
            }
            result.append(translateWord(words[k]));
        }
        return result.toString();
    }

    private String translateWord(String word) {
        if (word.isEmpty()) {
            return word;
        }

        int len = word.length();
        char first = Character.toLowerCase(word.charAt(0));

        // Rule 1: begins with a vowel, or starts with "xr" or "yt".
        if (VOWELS.contains(first) || word.startsWith("xr") || word.startsWith("yt")) {
            return word + "ay";
        }

        // Scan the leading consonant cluster. A 'y' after at least one
        // consonant acts as a vowel boundary (rule 4).
        int idx = 0;
        while (idx < len) {
            char ch = Character.toLowerCase(word.charAt(idx));
            if (VOWELS.contains(ch)) {
                break;
            }
            if (ch == 'y' && idx > 0) {
                break;
            }
            idx++;
        }

        int split;
        if (idx < len && Character.toLowerCase(word.charAt(idx)) == 'y') {
            // Rule 4: consonants before 'y' move to the end, 'y' stays.
            split = idx;
        } else if (idx < len
                && idx > 0
                && Character.toLowerCase(word.charAt(idx)) == 'u'
                && Character.toLowerCase(word.charAt(idx - 1)) == 'q') {
            // Rule 3: move the consonants plus the "qu" to the end.
            split = idx + 1;
        } else {
            // Rule 2: move the leading consonant cluster.
            split = idx;
        }

        return word.substring(split) + word.substring(0, split) + "ay";
    }
}
