package com.example;

import java.util.*;
import java.util.function.*;
import java.util.stream.*;

public class LambdaEdgeCases {

    // Simple single-line lambdas as fields
    private Runnable simpleRunnable = () -> System.out.println("hello");
    private Supplier<String> supplier = () -> "value";
    private Consumer<String> consumer = s -> System.out.println(s);
    private Function<String, Integer> parser = s -> Integer.parseInt(s);
    private BiFunction<String, String, String> concat = (a, b) -> a + b;

    // Lambda with parenthesized params
    private Comparator<String> byLength = (String a, String b) -> a.length() - b.length();

    // Multi-line lambda with braces
    private Comparator<String> complexComp = (a, b) -> {
        if (a == null) return -1;
        if (b == null) return 1;
        return a.compareTo(b);
    };

    // Method reference as field
    private Function<String, String> upper = String::toUpperCase;
    private Comparator<String> natural = Comparator.naturalOrder();

    // Lambda assigned via static method
    private Predicate<String> notEmpty = Predicate.not(String::isEmpty);

    // Chained lambda / functional field
    private Comparator<String> chainedComp = Comparator.comparing(String::length)
        .thenComparing(String::toLowerCase);

    // Lambda in a collection initializer
    private List<Runnable> tasks = List.of(
        () -> System.out.println("task1"),
        () -> System.out.println("task2"),
        () -> System.out.println("task3")
    );

    // Map with lambda values
    private Map<String, Function<String, String>> transformers = Map.of(
        "upper", s -> s.toUpperCase(),
        "lower", s -> s.toLowerCase(),
        "trim", String::trim
    );

    // Multi-line lambda with complex body
    private Function<List<String>, Map<String, Integer>> indexer = items -> {
        Map<String, Integer> result = new HashMap<>();
        for (int i = 0; i < items.size(); i++) {
            result.put(items.get(i), i);
        }
        return result;
    };

    // Regular fields (should still be detected)
    private String name = "test";
    private int count = 42;

    // Business methods that USE lambdas internally
    public List<String> filterAndSort(List<String> input) {
        return input.stream()
            .filter(s -> s != null && !s.isEmpty())
            .sorted((a, b) -> a.compareToIgnoreCase(b))
            .collect(Collectors.toList());
    }

    public Map<String, List<String>> groupByLength(List<String> items) {
        return items.stream()
            .collect(Collectors.groupingBy(
                s -> String.valueOf(s.length()),
                Collectors.toList()
            ));
    }

    public void processAll(List<String> items) {
        items.forEach(item -> {
            String processed = item.trim().toLowerCase();
            consumer.accept(processed);
        });
    }

    // Method returning a lambda
    public Predicate<String> createFilter(String prefix) {
        return s -> s.startsWith(prefix);
    }

    // Method with lambda parameter
    public <T> List<T> transform(List<String> input, Function<String, T> mapper) {
        return input.stream().map(mapper).collect(Collectors.toList());
    }

    // Getter (should be classified as getter)
    public String getName() {
        return name;
    }
}
