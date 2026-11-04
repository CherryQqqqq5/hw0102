class PhoneNumber {

    private final String number;

    PhoneNumber(String numberString) {
        for (int i = 0; i < numberString.length(); i++) {
            if (Character.isLetter(numberString.charAt(i))) {
                throw new IllegalArgumentException("letters not permitted");
            }
        }

        StringBuilder digits = new StringBuilder();
        for (int i = 0; i < numberString.length(); i++) {
            char c = numberString.charAt(i);
            if (c >= '0' && c <= '9') {
                digits.append(c);
            } else if (!isAllowedPunctuation(c)) {
                throw new IllegalArgumentException("punctuations not permitted");
            }
        }

        String cleaned = digits.toString();

        if (cleaned.length() < 10) {
            throw new IllegalArgumentException("must not be fewer than 10 digits");
        }
        if (cleaned.length() > 11) {
            throw new IllegalArgumentException("must not be greater than 11 digits");
        }
        if (cleaned.length() == 11) {
            if (cleaned.charAt(0) != '1') {
                throw new IllegalArgumentException("11 digits must start with 1");
            }
            cleaned = cleaned.substring(1);
        }

        if (cleaned.charAt(0) == '0') {
            throw new IllegalArgumentException("area code cannot start with zero");
        }
        if (cleaned.charAt(0) == '1') {
            throw new IllegalArgumentException("area code cannot start with one");
        }
        if (cleaned.charAt(3) == '0') {
            throw new IllegalArgumentException("exchange code cannot start with zero");
        }
        if (cleaned.charAt(3) == '1') {
            throw new IllegalArgumentException("exchange code cannot start with one");
        }

        this.number = cleaned;
    }

    String getNumber() {
        return number;
    }

    private static boolean isAllowedPunctuation(char c) {
        return c == '+' || c == '-' || c == '.' || c == ' ' || c == '(' || c == ')';
    }
}
