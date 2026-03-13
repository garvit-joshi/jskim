package com.example;

public class SwitchExprFields {
    private int x = 5;

    private String label = switch(x) {
        case 1 -> "one";
        case 2 -> "two";
        default -> "other";
    };

    private int category = switch(label) {
        case "one", "two" -> 1;
        default -> {
            System.out.println("default");
            yield 0;
        }
    };

    public String getLabel() {
        return label;
    }
}
