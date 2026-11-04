import java.util.regex.Matcher;
import java.util.regex.Pattern;

class PigLatinTranslator {

    private static final Pattern VOWEL_START = Pattern.compile("^(?:[aeiou].*|xr.*|yt.*)$");
    private static final Pattern QU_PREFIX = Pattern.compile("^([^aeiou]*qu)(.*)$");
    private static final Pattern Y_PREFIX = Pattern.compile("^([^aeiou]+)(y.*)$");
    private static final Pattern CONSONANT_PREFIX = Pattern.compile("^([^aeiou]+)(.*)$");

    public String translate(String phrase) {
        if (phrase == null || phrase.isEmpty()) {
            return "";
        }

        String[] words = phrase.split("\\s+");
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
        if (VOWEL_START.matcher(word).matches()) {
            return word + "ay";
        }

        Matcher matcher = QU_PREFIX.matcher(word);
        if (matcher.matches()) {
            return matcher.group(2) + matcher.group(1) + "ay";
        }

        matcher = Y_PREFIX.matcher(word);
        if (matcher.matches()) {
            return matcher.group(2) + matcher.group(1) + "ay";
        }

        matcher = CONSONANT_PREFIX.matcher(word);
        if (matcher.matches()) {
            return matcher.group(2) + matcher.group(1) + "ay";
        }

        return word + "ay";
    }
}
