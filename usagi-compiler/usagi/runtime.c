/* Embedded verbatim in generated output; not a separate executable. */
#define _CRT_SECURE_NO_WARNINGS 1
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif

extern const char *us_source;

/* Value semantics: returning or assigning a string copies its bytes. */
typedef struct { char data[4096]; } us_string;

_Noreturn void us_fail(const char *message, int line, int column) {
    fprintf(stderr, "%s:%d:%d: runtime error: %s\n", us_source, line, column, message);
    exit(2);
}

/* Function-owned arrays; scope checkpoints also handle break and continue. */
typedef struct us_array {
    int64_t length;
    int64_t *data;
    struct us_array *previous;
} us_array;

us_array *us_array_new(us_array **owner, int64_t length, int l, int c) {
    if (length < 0) us_fail("negative array size", l, c);
    if ((uint64_t)length > SIZE_MAX / sizeof(int64_t)) us_fail("array size out of range", l, c);
    us_array *array = malloc(sizeof(*array));
    if (!array) us_fail("array allocation failed", l, c);
    array->data = length ? calloc((size_t)length, sizeof(int64_t)) : NULL;
    if (length && !array->data) { free(array); us_fail("array allocation failed", l, c); }
    array->length = length;
    array->previous = *owner;
    *owner = array;
    return array;
}

int64_t *us_array_at(us_array *array, int64_t index, int l, int c) {
    if (index < 0 || index >= array->length) us_fail("array index out of bounds", l, c);
    return &array->data[index];
}

void us_array_cleanup(us_array **owner, us_array *checkpoint) {
    while (*owner != checkpoint) {
        us_array *array = *owner;
        *owner = array->previous;
        free(array->data);
        free(array);
    }
}

int64_t us_real_to_int(double value, int l, int c) {
    /* (double)INT64_MAX rounds up to 2^63: use an exclusive upper bound. */
    if (!isfinite(value) || value < -9223372036854775808.0 || value >= 9223372036854775808.0)
        us_fail("real-to-integer conversion out of range", l, c);
    return (int64_t)value;
}

int64_t us_count(int64_t value, int l, int c) {
    if (value < 0) us_fail("negative repetition count", l, c);
    return value;
}

us_string us_string_literal(const char *text, int l, int c) {
    us_string value = {{0}};
    size_t length = strlen(text);
    if (length > 4095) us_fail("string too long (maximum 4095 bytes)", l, c);
    memcpy(value.data, text, length + 1);
    return value;
}

int64_t us_i_add(int64_t a, int64_t b, int l, int c) {
    if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b))
        us_fail("integer overflow", l, c);
    return a + b;
}

int64_t us_i_sub(int64_t a, int64_t b, int l, int c) {
    if ((b > 0 && a < INT64_MIN + b) || (b < 0 && a > INT64_MAX + b))
        us_fail("integer overflow", l, c);
    return a - b;
}

int64_t us_i_mul(int64_t a, int64_t b, int l, int c) {
    if (a > 0) {
        if ((b > 0 && a > INT64_MAX / b) || (b < 0 && b < INT64_MIN / a))
            us_fail("integer overflow", l, c);
    } else if (a < 0) {
        if ((b > 0 && a < INT64_MIN / b) || (b < 0 && a < INT64_MAX / b))
            us_fail("integer overflow", l, c);
    }
    return a * b;
}

void us_i_divisor(int64_t a, int64_t b, int l, int c) {
    if (b == 0) us_fail("division by zero", l, c);
    if (a == INT64_MIN && b == -1) us_fail("integer overflow", l, c);
}

int64_t us_i_div(int64_t a, int64_t b, int l, int c) {
    us_i_divisor(a, b, l, c);
    return a / b;
}

int64_t us_i_mod(int64_t a, int64_t b, int l, int c) {
    us_i_divisor(a, b, l, c);
    return a % b;
}

double us_finite(double value, int l, int c) {
    if (!isfinite(value)) us_fail("non-finite real result", l, c);
    return value;
}

double us_r_add(double a, double b, int l, int c) { return us_finite(a + b, l, c); }
double us_r_sub(double a, double b, int l, int c) { return us_finite(a - b, l, c); }
double us_r_mul(double a, double b, int l, int c) { return us_finite(a * b, l, c); }
double us_r_div(double a, double b, int l, int c) {
    if (b == 0.0) us_fail("division by zero", l, c);
    return us_finite(a / b, l, c);
}

/* One complete line per input statement, with a bounded 4095-byte payload. */
void us_read_line(char *buffer, int l, int c) {
#ifdef _WIN32
    DWORD mode;
    HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
    if (GetConsoleMode(input, &mode)) {
        WCHAR wide[4096];
        int length = 0;
        for (;;) {
            WCHAR ch;
            DWORD read_count;
            if (!ReadConsoleW(input, &ch, 1, &read_count, NULL) || read_count == 0)
                us_fail("failed to read console input", l, c);
            if (ch == 26 && length == 0) us_fail("unexpected end of input", l, c);
            if (ch == L'\n') break;
            if (ch == L'\r') continue;
            if (ch == 0) us_fail("invalid input: NUL byte", l, c);
            if (length == 4095) us_fail("input line too long (maximum 4095 bytes)", l, c);
            wide[length++] = ch;
        }
        if (length == 0) { buffer[0] = '\0'; return; }
        int bytes = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide, length, buffer, 4095, NULL, NULL);
        if (bytes == 0) us_fail("invalid Unicode or input line too long (maximum 4095 bytes)", l, c);
        buffer[bytes] = '\0';
        return;
    }
#endif
    size_t count = 0;
    int ch;
    while ((ch = getchar()) != '\n' && ch != EOF) {
        if (count == 4095) us_fail("input line too long (maximum 4095 bytes)", l, c);
        if (ch == 0) us_fail("invalid input: NUL byte", l, c);
        buffer[count++] = (char)ch;
    }
    if (ferror(stdin)) us_fail("failed to read input", l, c);
    if (count == 0 && ch == EOF) us_fail("unexpected end of input", l, c);
    buffer[count] = '\0';
}

int us_digit(char c) { return c >= '0' && c <= '9'; }

/* Reject C-only hex, NaN and infinity spellings before calling strto*. */
int us_valid_decimal(const char *text, int real) {
    const char *p = text;
    int digits = 0;
    while (isspace((unsigned char)*p)) ++p;
    if (*p == '+' || *p == '-') ++p;
    while (us_digit(*p)) { ++digits; ++p; }
    if (real && *p == '.') {
        ++p;
        while (us_digit(*p)) { ++digits; ++p; }
    }
    if (digits == 0) return 0;
    if (real && (*p == 'e' || *p == 'E')) {
        ++p;
        if (*p == '+' || *p == '-') ++p;
        if (!us_digit(*p)) return 0;
        while (us_digit(*p)) ++p;
    }
    while (isspace((unsigned char)*p)) ++p;
    return *p == '\0';
}

/* Numeric reads share a cursor so a later read can consume the next field.
   String reads begin on the next physical line once numeric fields are exhausted. */
static char us_input_line[4096];
static size_t us_input_cursor = 0;
static int us_input_pending = 0;

void us_read_token(char *buffer, int l, int c) {
    for (;;) {
        if (!us_input_pending) {
            us_read_line(us_input_line, l, c);
            us_input_cursor = 0;
            us_input_pending = 1;
        }
        while (isspace((unsigned char)us_input_line[us_input_cursor])) ++us_input_cursor;
        if (!us_input_line[us_input_cursor]) { us_input_pending = 0; continue; }
        size_t count = 0;
        while (us_input_line[us_input_cursor] && !isspace((unsigned char)us_input_line[us_input_cursor]))
            buffer[count++] = us_input_line[us_input_cursor++];
        buffer[count] = '\0';
        size_t remainder = us_input_cursor;
        while (isspace((unsigned char)us_input_line[remainder])) ++remainder;
        if (!us_input_line[remainder]) us_input_pending = 0;
        return;
    }
}

int64_t us_read_i(int l, int c) {
    char buffer[4096];
    char *end;
    us_read_token(buffer, l, c);
    if (!us_valid_decimal(buffer, 0)) us_fail("expected a decimal integer", l, c);
    errno = 0;
    intmax_t value = strtoimax(buffer, &end, 10);
    if (errno == ERANGE || value < INT64_MIN || value > INT64_MAX)
        us_fail("integer input out of range", l, c);
    return (int64_t)value;
}

double us_read_r(int l, int c) {
    char buffer[4096];
    char *end;
    us_read_token(buffer, l, c);
    if (!us_valid_decimal(buffer, 1)) us_fail("expected a decimal real number", l, c);
    errno = 0;
    double value = strtod(buffer, &end);
    if (errno == ERANGE || !isfinite(value)) us_fail("real input out of range", l, c);
    return value;
}

us_string us_read_s(int l, int c) {
    us_string value = {{0}};
    if (us_input_pending) us_fail("unread numeric fields before string input", l, c);
    us_read_line(value.data, l, c);
    return value;
}

void us_print_s(us_string value, int l, int c) {
#ifdef _WIN32
    DWORD mode;
    HANDLE output = GetStdHandle(STD_OUTPUT_HANDLE);
    if (GetConsoleMode(output, &mode)) {
        WCHAR wide[4097];
        int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data, -1, wide, 4096);
        if (length == 0) us_fail("invalid UTF-8 string", l, c);
        wide[length - 1] = L'\n';
        DWORD written;
        if (fflush(stdout) == EOF || !WriteConsoleW(output, wide, (DWORD)length, &written, NULL) || written != (DWORD)length)
            us_fail("failed to write console output", l, c);
        return;
    }
#endif
    if (fputs(value.data, stdout) == EOF || putchar('\n') == EOF || fflush(stdout) == EOF)
        us_fail("failed to write output", l, c);
}

void us_print_i(int64_t value, int l, int c) {
    if (printf("%" PRId64 "\n", value) < 0 || fflush(stdout) == EOF)
        us_fail("failed to write output", l, c);
}

void us_print_r(double value, int l, int c) {
    if (printf("%.15g\n", value) < 0 || fflush(stdout) == EOF)
        us_fail("failed to write output", l, c);
}
