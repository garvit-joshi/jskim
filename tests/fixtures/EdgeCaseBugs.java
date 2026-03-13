package com.example.edgecases;

import java.util.*;
import java.util.function.Function;
import java.time.LocalDateTime;

// =============================================================================
// EdgeCaseBugs.java — Test file that triggers multiple jskim bugs.
//
// Bug 1: Getter false positive (classify_method)
//   - getaway() and isolate() are real business methods but classified as getters
//     because classify_method doesn't check for uppercase after "get"/"is" prefix.
//
// Bug 2: Multi-variable field declarations (extract_field_info)
//   - "int x, y, z;" only reports the last variable (z). x and y are lost.
//
// Bug 3: Record compact constructors (METHOD_NODES)
//   - Inner record's compact constructor is invisible (compact_constructor_declaration
//     is not in METHOD_NODES).
//
// Bug 4: Block comment opening "/*" not captured in backwards walk (extract_method)
//   - Only "/**", "*", "@", "//" are checked. Regular "/* comment" is missed.
//
// Bug 5: sealed/permits clause not shown (build_class_declaration_text)
//   - "sealed class ... permits ..." loses the permits clause in output.
//
// Bug 6: Annotation type declarations invisible (INNER_TYPE_NODES)
//   - @interface is not in INNER_TYPE_NODES so annotation types inside a class
//     (or as top-level) are never reported.
// =============================================================================

public class EdgeCaseBugs {

    // --- Bug 2: Multi-variable field declarations ---
    // Only the LAST variable in each declaration is captured.
    // Expected: int x, int y, int z  |  Actual: int z
    private int x, y, z;
    private String firstName, lastName;
    private double amount;

    // --- Bug 1: Getter false positive ---
    // These are business methods, NOT getters.
    // "getaway" is a word, not get+Away. "isolate" is a word, not is+Olate.

    /**
     * Plan an escape route — this is a business method, not a getter.
     */
    public String getaway() {
        return "escaped via route " + firstName;
    }

    /**
     * Isolate a component — business logic, not a boolean accessor.
     */
    public boolean isolate() {
        return x > 0 && y > 0;
    }

    // Real getters for comparison (should still be classified as getters)
    public double getAmount() {
        return amount;
    }

    public boolean isPositive() {
        return amount > 0;
    }

    // --- Bug 4: Block comment not captured in backwards walk ---
    // When using skim_method.py to extract processData, the opening "/*" line
    // of this block comment will be missed (only "/**", "*", "@", "//" checked).

    /* This is a regular block comment
     * explaining processData behavior.
     * It is NOT a Javadoc comment.
     */
    public Map<String, Integer> processData(List<String> input) {
        Map<String, Integer> result = new HashMap<>();
        for (String s : input) {
            result.put(s, s.length());
        }
        return result;
    }

    // --- Bug 6: Annotation type not detected as inner type ---
    // This @interface will not appear in inner types output.
    public @interface ValidInput {
        String message() default "Invalid input";
        Class<?>[] groups() default {};
    }

    // --- Bug 3: Record compact constructor not detected ---
    // The compact constructor inside this record will be invisible.
    public record Coordinate(double lat, double lon) {
        // This compact constructor won't show in method listing
        public Coordinate {
            if (lat < -90 || lat > 90) {
                throw new IllegalArgumentException("Invalid latitude: " + lat);
            }
            if (lon < -180 || lon > 180) {
                throw new IllegalArgumentException("Invalid longitude: " + lon);
            }
        }

        public double distanceTo(Coordinate other) {
            double dx = this.lat - other.lat;
            double dy = this.lon - other.lon;
            return Math.sqrt(dx * dx + dy * dy);
        }
    }

    // Normal method to verify non-buggy paths still work
    public void reset() {
        this.x = 0;
        this.y = 0;
        this.z = 0;
        this.amount = 0.0;
    }

    // Multi-parameter setter — should NOT be classified as setter
    public void setCoordinates(int x, int y, int z) {
        this.x = x;
        this.y = y;
        this.z = z;
    }

    @Override
    public String toString() {
        return "EdgeCaseBugs{x=" + x + ", y=" + y + ", z=" + z + "}";
    }
}
