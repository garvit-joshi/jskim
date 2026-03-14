package com.example.modern;

import java.util.List;

/**
 * Fixture covering Java 16-23 features for testing.
 */
public sealed interface Shape<T> permits ModernJavaFeatures.Circle, ModernJavaFeatures.Rectangle {
    double area();
    double perimeter();
}

class Circle implements Shape<Double> {
    private final double radius;

    Circle(double radius) {
        this.radius = radius;
    }

    @Override
    public double area() {
        return Math.PI * radius * radius;
    }

    @Override
    public double perimeter() {
        return 2 * Math.PI * radius;
    }

    public String describe(Object obj) {
        // Pattern matching instanceof (Java 16)
        if (obj instanceof String s) {
            return s.toUpperCase();
        }
        // Switch pattern matching (Java 21)
        return switch (obj) {
            case Integer i -> String.format("int %d", i);
            case Double d when d > 0 -> String.format("positive %.2f", d);
            default -> obj.toString();
        };
    }
}

record Point(int x, int y) implements Comparable<Point> {
    // Compact constructor
    Point {
        if (x < 0 || y < 0) throw new IllegalArgumentException();
    }

    public double distance() {
        return Math.sqrt(x * x + y * y);
    }

    @Override
    public int compareTo(Point other) {
        return Double.compare(this.distance(), other.distance());
    }
}

record Response<T>(T data, String message, int code) {
    public boolean isSuccess() {
        return code >= 200 && code < 300;
    }
}

class Rectangle implements Shape<Double> {
    private final double width;
    private final double height;

    Rectangle(double width, double height) {
        this.width = width;
        this.height = height;
    }

    @Override
    public double area() {
        return width * height;
    }

    @Override
    public double perimeter() {
        return 2 * (width + height);
    }
}
