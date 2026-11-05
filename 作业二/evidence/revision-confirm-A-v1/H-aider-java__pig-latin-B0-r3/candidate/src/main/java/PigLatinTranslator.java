class PigLatinTranslator {
    public String translate(String phrase) {
        String[] words = phrase.split(" ", -1);
        StringBuilder translated = new StringBuilder();
        for (int i = 0; i < words.length; i++) {
            if (i > 0) {
                translated.append(' ');
            }
            translated.append(translateWord(words[i]));
        }
        return translated.toString();
    }

    private String translateWord(String word) {
        if (word.isEmpty()) {
            return word;
        }

        char first = Character.toLowerCase(word.charAt(0));
        if (isVowel(first) || word.startsWith("xr") || word.startsWith("yt")) {
            return word + "ay";
        }

        int quIndex = word.indexOf("qu");
        if (quIndex >= 0 && allConsonants(word, 0, quIndex)) {
            return word.substring(quIndex + 2) + word.substring(0, quIndex + 2) + "ay";
        }

        for (int i = 1; i < word.length(); i++) {
            if (Character.toLowerCase(word.charAt(i)) == 'y' && allConsonants(word, 0, i)) {
                return word.substring(i) + word.substring(0, i) + "ay";
            }
        }

        int i = 0;
        while (i < word.length() && !isVowel(Character.toLowerCase(word.charAt(i)))) {
            i++;
        }
        return word.substring(i) + word.substring(0, i) + "ay";
    }

    private boolean isVowel(char c) {
        return "aeiou".indexOf(c) >= 0;
    }

    private boolean allConsonants(String word, int start, int end) {
        for (int i = start; i < end; i++) {
            if (isVowel(Character.toLowerCase(word.charAt(i)))) {
                return false;
            }
        }
        return true;
    }
}
