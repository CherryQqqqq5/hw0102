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

        char first = Character.toLowerCase(word.charAt(0));
        if (isVowel(first) || word.toLowerCase().startsWith("xr") || word.toLowerCase().startsWith("yt")) {
            return word + "ay";
        }

        int n = word.length();
        int split = 0;
        while (split < n) {
            char c = Character.toLowerCase(word.charAt(split));
            if (isVowel(c)) {
                break;
            }
            if (c == 'y' && split > 0) {
                break;
            }
            if (c == 'q' && split + 1 < n && Character.toLowerCase(word.charAt(split + 1)) == 'u') {
                split += 2;
                break;
            }
            split++;
        }

        return word.substring(split) + word.substring(0, split) + "ay";
    }

    private boolean isVowel(char c) {
        return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';
    }
}
