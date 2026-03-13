package com.example;

public enum Status {
    ACTIVE("active"),
    PENDING("pending", 1),
    DONE("done") {
        @Override
        public String display() { return "Completed"; }
    };

    private final String label;
    private int priority;

    Status(String label) {
        this.label = label;
    }

    Status(String label, int priority) {
        this.label = label;
        this.priority = priority;
    }

    public String getLabel() {
        return label;
    }

    public boolean isTerminal() {
        return this == DONE;
    }
}
