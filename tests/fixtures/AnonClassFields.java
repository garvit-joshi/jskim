package com.example;

import java.util.HashMap;
import java.util.Map;

public class AnonClassFields {
    private Runnable task = new Runnable() {
        @Override
        public void run() {
            System.out.println("running");
        }
    };

    private Map<String, Object> map = new HashMap<>() {{
        put("key", "value");
        put("key2", "value2");
    }};

    private Comparable<String> custom = new Comparable<String>() {
        @Override
        public int compareTo(String o) {
            return 0;
        }
    };

    public void execute() {
        task.run();
    }
}
