import org.junit.jupiter.api.Test;

class JavaEnvironmentCheck {
    @Test
    void dependenciesAreAvailable() {
        org.assertj.core.api.Assertions.assertThat(1).isEqualTo(1);
    }
}
