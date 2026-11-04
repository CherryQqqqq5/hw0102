import java.util.Arrays;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

class PigLatinTranslator {

    private static final Pattern VOWEL_START = Pattern.compile("^([aeiou]|xr|yt).*");
    private static final Pattern QU_START = Pattern.compile("^([^aeiou]*qu)(.*)");
    private static final Pattern Y_AFTER_CONSONANTS = Pattern.compile("^([^aeiou]+)(y.*)");
    private static final Pattern CONSONANT_START = Pattern.compile("^([^aeiou]+)(.*)");

    public String translate(String word) {
        return Arrays.stream(word.split(" "))
                .map(this::translateWord)
                .collect(Collectors.joining(" "));
    }

    private String translateWord(String word) {
        if (word.isEmpty()) {
            return word;
        }

        // Rule 1: starts with a vowel, or with "xr" / "yt"
        if (VOWEL_START.matcher(word).matches()) {
            return word + "ay";
        }

        // Rule 3: zero or more consonants followed by "qu"
        Matcher m = QU_START.matcher(word);
        if (m.matches()) {
            return m.group(2) + m.group(1) + "ay";
        }

        // Rule 4: one or more consonants followed by "y"
        m = Y_AFTER_CONSONANTS.matcher(word);
        if (m.matches()) {
            return m.group(2) + m.group(1) + "ay";
        }

        // Rule 2: one or more leading consonants
        m = CONSONANT_START.matcher(word);
        if (m.matches()) {
            return m.group(2) + m.group(1) + "ay";
        }

        return word + "ay";
    }
}
