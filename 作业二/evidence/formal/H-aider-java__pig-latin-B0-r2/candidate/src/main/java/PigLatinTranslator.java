class PigLatinTranslator {
    public String translate(String phrase) {
        String[] words = phrase.split(" ");
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

        if (isVowel(word.charAt(0)) || word.startsWith("xr") || word.startsWith("yt")) {
            return word + "ay";
        }

        // Rule 3: optional consonants followed by "qu"
        for (int i = 0; i < word.length() - 1; i++) {
            if (word.charAt(i) == 'q' && word.charAt(i + 1) == 'u' && onlyConsonantsBefore(word, i)) {
                int split = i + 2;
                return word.substring(split) + word.substring(0, split) + "ay";
            }
        }

        // Rule 4: one or more consonants followed by "y"
        for (int i = 1; i < word.length(); i++) {
            if (word.charAt(i) == 'y' && onlyConsonantsBefore(word, i)) {
                return word.substring(i) + word.substring(0, i) + "ay";
            }
        }

        // Rule 2: leading consonant cluster
        int i = 0;
        while (i < word.length() && !isVowel(word.charAt(i))) {
            i++;
        }
        return word.substring(i) + word.substring(0, i) + "ay";
    }

    private boolean onlyConsonantsBefore(String word, int end) {
        for (int i = 0; i < end; i++) {
            if (isVowel(word.charAt(i))) {
                return false;
            }
        }
        return true;
    }

    private boolean isVowel(char c) {
        return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';
    }
}
