import java.util.Arrays;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

class PigLatinTranslator {
    private static final Pattern VOWEL_START = Pattern.compile("^(?:[aeiou]|xr|yt).*");
    private static final Pattern QU_START = Pattern.compile("^([^aeiou]*qu)(.*)$");
    private static final Pattern Y_AFTER_CONSONANTS = Pattern.compile("^([^aeiouy]+)(y.*)$");
    private static final Pattern CONSONANT_START = Pattern.compile("^([^aeiou]+)(.*)$");

    public String translate(String phrase) {
        return Arrays.stream(phrase.split(" "))
                .map(this::translateWord)
                .collect(Collectors.joining(" "));
    }

    private String translateWord(String word) {
        if (VOWEL_START.matcher(word).matches()) {
            return word + "ay";
        }

        Matcher matcher = QU_START.matcher(word);
        if (matcher.matches()) {
            return matcher.group(2) + matcher.group(1) + "ay";
        }

        matcher = Y_AFTER_CONSONANTS.matcher(word);
        if (matcher.matches()) {
            return matcher.group(2) + matcher.group(1) + "ay";
        }

        matcher = CONSONANT_START.matcher(word);
        if (matcher.matches()) {
            return matcher.group(2) + matcher.group(1) + "ay";
        }

        return word + "ay";
    }
}
