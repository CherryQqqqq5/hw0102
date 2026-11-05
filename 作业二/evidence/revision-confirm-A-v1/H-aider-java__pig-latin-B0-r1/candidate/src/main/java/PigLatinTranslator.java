class PigLatinTranslator {
    public String translate(String phrase) {
        String[] words = phrase.split(" ", -1);
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

        int split = 0;
        while (split < word.length() && !isVowel(word.charAt(split))) {
            if (word.charAt(split) == 'q'
                    && split + 1 < word.length()
                    && word.charAt(split + 1) == 'u') {
                split += 2;
                break;
            }

            if (word.charAt(split) == 'y' && split > 0) {
                break;
            }

            split++;
        }

        return word.substring(split) + word.substring(0, split) + "ay";
    }

    private boolean isVowel(char character) {
        return "aeiou".indexOf(character) >= 0;
    }
}
