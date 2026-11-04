import java.util.regex.Matcher;
import java.util.regex.Pattern;

class PigLatinTranslator {
    private static final String VOWELS = "aeiou";

    public String translate(String phrase) {
        String[] words = phrase.trim().split("\\s+");
        StringBuilder translated = new StringBuilder();

        for (String word : words) {
            if (translated.length() > 0) {
                translated.append(' ');
            }
            translated.append(translateWord(word));
        }

        return translated.toString();
    }

    private String translateWord(String word) {
        if (word.isEmpty()) {
            return word;
        }

        // Rule 1: begins with a vowel, or starts with "xr" or "yt".
        if (VOWELS.indexOf(word.charAt(0)) >= 0
                || word.startsWith("xr")
                || word.startsWith("yt")) {
            return word + "ay";
        }

        // Rule 3: zero or more consonants followed by "qu".
        Matcher qu = Pattern.compile("^([^aeiou]*qu)").matcher(word);
        if (qu.find()) {
            return word.substring(qu.end()) + qu.group(1) + "ay";
        }

        // Rule 4: one or more consonants followed by "y".
        Matcher y = Pattern.compile("^([^aeiou]+)y").matcher(word);
        if (y.find()) {
            return word.substring(y.end() - 1) + y.group(1) + "ay";
        }

        // Rule 2: one or more leading consonants.
        int consonantCount = 0;
        while (consonantCount < word.length()
                && VOWELS.indexOf(word.charAt(consonantCount)) < 0) {
            consonantCount++;
        }

        return word.substring(consonantCount)
                + word.substring(0, consonantCount)
                + "ay";
    }
}
