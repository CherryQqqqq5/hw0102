import java.util.Arrays;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

class PigLatinTranslator {

    private static final Pattern VOWEL_START = Pattern.compile("^([aeiou]|xr|yt).*");
    private static final Pattern QU_START = Pattern.compile("^([^aeiou]*qu)(.*)$");
    private static final Pattern Y_START = Pattern.compile("^([^aeiou]+)(y.*)$");
    private static final Pattern CONSONANT_START = Pattern.compile("^([^aeiou]+)(.*)$");

    public String translate(String word) {
        return Arrays.stream(word.split(" "))
                .map(this::translateWord)
                .collect(Collectors.joining(" "));
    }

    private String translateWord(String word) {
        String lower = word.toLowerCase();

        if (VOWEL_START.matcher(lower).matches()) {
            return word + "ay";
        }

        Matcher matcher = QU_START.matcher(lower);
        if (matcher.matches()) {
            return moveToEnd(word, matcher.group(1).length());
        }

        matcher = Y_START.matcher(lower);
        if (matcher.matches()) {
            return moveToEnd(word, matcher.group(1).length());
        }

        matcher = CONSONANT_START.matcher(lower);
        if (matcher.matches()) {
            return moveToEnd(word, matcher.group(1).length());
        }

        return word + "ay";
    }

    private String moveToEnd(String word, int prefixLength) {
        return word.substring(prefixLength) + word.substring(0, prefixLength) + "ay";
    }
}
