import java.util.regex.Matcher;
import java.util.regex.Pattern;

class PigLatinTranslator {

    // Rule 1: starts with a vowel, or with "xr"/"yt"
    private static final Pattern VOWEL_START = Pattern.compile("^(?:xr|yt|[aeiou]).*$");

    // Rule 3: zero or more consonants followed by "qu"
    private static final Pattern QU_CLUSTER = Pattern.compile("^([^aeiou]*qu)(.*)$");

    // Rule 4: one or more consonants followed by "y"
    private static final Pattern Y_CLUSTER = Pattern.compile("^([^aeiou]+)y(.*)$");

    // Rule 2: one or more leading consonants
    private static final Pattern CONSONANT_CLUSTER = Pattern.compile("^([^aeiou]+)(.*)$");

    public String translate(String phrase) {
        String[] words = phrase.trim().split("\\s+");
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

        if (VOWEL_START.matcher(word).matches()) {
            return word + "ay";
        }

        Matcher matcher = QU_CLUSTER.matcher(word);
        if (matcher.matches()) {
            return matcher.group(2) + matcher.group(1) + "ay";
        }

        matcher = Y_CLUSTER.matcher(word);
        if (matcher.matches()) {
            // the "y" stays at the front and acts as the vowel
            return "y" + matcher.group(2) + matcher.group(1) + "ay";
        }

        matcher = CONSONANT_CLUSTER.matcher(word);
        if (matcher.matches()) {
            return matcher.group(2) + matcher.group(1) + "ay";
        }

        return word + "ay";
    }
}
