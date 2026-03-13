package com.example.edgecases;

import java.util.List;

// =============================================================================
// SealedAndMultiClass.java — Tests two jskim bugs:
//
// Bug 5: sealed/permits clause lost in output
//   - "sealed class Shape permits Circle, Rectangle" shown as just "sealed class Shape"
//   - build_class_declaration_text doesn't handle the "permits" node
//
// Bug 3 (variant): Multiple top-level classes ignored
//   - Only the first class (Shape) is processed. Circle and Rectangle are invisible.
//   - All three scripts break on the first type declaration due to `break`.
//
// Expected output should show:
//   - "public sealed class Shape permits Circle, Rectangle" (with permits clause)
//   - Circle, Rectangle classes listed or at least mentioned
//
// Actual output:
//   - "public sealed class Shape" (permits clause missing)
//   - Circle and Rectangle are completely invisible
// =============================================================================

public sealed class SealedAndMultiClass permits Circle, Rectangle {
    private final String color;

    public SealedAndMultiClass(String color) {
        this.color = color;
    }

    public String getColor() {
        return color;
    }

    public double area() {
        return 0.0;
    }
}

final class Circle extends SealedAndMultiClass {
    private final double radius;

    public Circle(String color, double radius) {
        super(color);
        this.radius = radius;
    }

    @Override
    public double area() {
        return Math.PI * radius * radius;
    }
}

final class Rectangle extends SealedAndMultiClass {
    private final double width;
    private final double height;

    public Rectangle(String color, double width, double height) {
        super(color);
        this.width = width;
        this.height = height;
    }

    @Override
    public double area() {
        return width * height;
    }
}
