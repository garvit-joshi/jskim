package com.example;

import java.util.Comparator;
import java.util.function.Function;

public class LambdaFields {
    private Comparator<String> comp = (a, b) -> {
        return a.compareTo(b);
    };

    private Runnable task = () -> System.out.println("hello");

    private Function<String, Integer> parser = (s) -> Integer.parseInt(s);

    private Comparator<Integer> reversed = Comparator.comparingInt(Integer::intValue).reversed();

    public void doWork() {
        task.run();
    }

    public int parse(String s) {
        return parser.apply(s);
    }
}
