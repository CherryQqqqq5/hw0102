class PigLatinTranslator {
    public String translate(String word) {
        String[] words = word.split(" ");
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < words.length; i++) {
            if (i > 0) {
                result.append(' ');
            }
            result.append(translateWord(words[i]));
        }
        return result.toString();
    }

    private String translateWord(String word) {
        if (word.isEmpty()) {
            return word;
        }

        // Rule 1: starts with a vowel, or with "xr"/"yt"
        char first = word.charAt(0);
        if (isVowel(first) || word.startsWith("xr") || word.startsWith("yt")) {
            return word + "ay";
        }

        int split = 0;
        boolean sawQu = false;
        while (split < word.length()) {
            char c = word.charAt(split);
            if (isVowel(c)) {
                break;
            }
            // Rule 4: a consonant cluster (one or more consonants) followed by 'y'
            if (c == 'y' && split > 0) {
                break;
            }
            // Rule 3: zero or more consonants followed by "qu"
            if (c == 'q' && split + 1 < word.length() && word.charAt(split + 1) == 'u') {
                split += 2;
                sawQu = true;
                break;
            }
            split++;
        }

        // Rule 2/3/4: move the leading cluster (including "qu") to the end.
        return word.substring(split) + word.substring(0, split) + "ay";
    }

    private boolean isVowel(char c) {
        return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';
    }
}
