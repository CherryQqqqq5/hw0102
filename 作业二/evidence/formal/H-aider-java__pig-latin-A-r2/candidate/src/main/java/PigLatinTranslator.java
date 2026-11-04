import java.util.StringJoiner;

class PigLatinTranslator {
    public String translate(String text) {
        StringJoiner translated = new StringJoiner(" ");
        for (String word : text.split(" ")) {
            translated.add(translateWord(word));
        }
        return translated.toString();
    }

    private String translateWord(String word) {
        if (word.isEmpty()) {
            return word;
        }

        // Rule 1: leading vowel, or special leading "xr"/"yt".
        if (isVowel(word.charAt(0))
                || word.startsWith("xr")
                || word.startsWith("yt")) {
            return word + "ay";
        }

        // Find the start of the part that stays at the front.
        int split = 0;
        while (split < word.length() && !isVowel(word.charAt(split))) {
            if (word.charAt(split) == 'y' && split > 0) {
                break;
            }
            split++;
        }

        // Rule 3: a consonant cluster ending in "qu" moves as a unit.
        if (split < word.length()
                && word.charAt(split) == 'u'
                && split > 0
                && word.charAt(split - 1) == 'q') {
            split++;
        }

        return word.substring(split) + word.substring(0, split) + "ay";
    }

    private boolean isVowel(char c) {
        return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';
    }
}
