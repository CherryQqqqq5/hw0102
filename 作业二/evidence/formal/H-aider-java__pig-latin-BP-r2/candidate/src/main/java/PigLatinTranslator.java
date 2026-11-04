class PigLatinTranslator {
    public String translate(String word) {
        String[] words = word.split("\\s+");
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < words.length; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(translateWord(words[i]));
        }
        return sb.toString();
    }

    private String translateWord(String w) {
        String lower = w.toLowerCase();
        // Rule 1: starts with a vowel, or "xr"/"yt"
        if (isVowel(lower.charAt(0)) || lower.startsWith("xr") || lower.startsWith("yt")) {
            return w + "ay";
        }
        // Rule 3: zero or more consonants followed by "qu"
        if (lower.matches("[^aeiou]*qu.*")) {
            int idx = lower.indexOf("qu") + 2;
            return w.substring(idx) + w.substring(0, idx) + "ay";
        }
        // Rule 4: one or more consonants followed by "y"
        if (lower.matches("[^aeiou]+y.*")) {
            int idx = lower.indexOf('y');
            return w.substring(idx) + w.substring(0, idx) + "ay";
        }
        // Rule 2: one or more leading consonants
        int idx = 0;
        while (idx < lower.length() && !isVowel(lower.charAt(idx))) {
            idx++;
        }
        return w.substring(idx) + w.substring(0, idx) + "ay";
    }

    private boolean isVowel(char c) {
        return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u';
    }
}
