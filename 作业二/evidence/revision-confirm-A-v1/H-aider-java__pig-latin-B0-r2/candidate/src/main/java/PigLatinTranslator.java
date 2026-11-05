import java.util.Arrays;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

class PigLatinTranslator {

    private static final Pattern RULE_ONE = Pattern.compile("^(?:[aeiou]|xr|yt)");
    private static final Pattern RULE_THREE = Pattern.compile("^([^aeiou]*qu)(.*)$");
    private static final Pattern RULE_FOUR = Pattern.compile("^([^aeiou]+)(y.*)$");
    private static final Pattern RULE_TWO = Pattern.compile("^([^aeiou]+)(.*)$");

    public String translate(String phrase) {
        return Arrays.stream(phrase.trim().split("\\s+"))
                .filter(word -> !word.isEmpty())
                .map(this::translateWord)
                .collect(Collectors.joining(" "));
    }

    private String translateWord(String word) {
        if (RULE_ONE.matcher(word).find()) {
            return word + "ay";
        }
        for (Pattern pattern : new Pattern[] {RULE_THREE, RULE_FOUR, RULE_TWO}) {
            Matcher matcher = pattern.matcher(word);
            if (matcher.matches()) {
                return matcher.group(2) + matcher.group(1) + "ay";
            }
        }
        return word + "ay";
    }
}
