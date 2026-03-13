package com.example;

import java.util.*;

public class InlineAnnotations {

    // Annotation on its own line (normal case)
    @Deprecated
    private String oldName;

    // Annotation + field on same line
    @Nullable private String nickname;

    // Annotation + field with initializer on same line
    @SuppressWarnings("unused") private int count = 0;

    // Multiple annotations + field on same line
    @Deprecated @Nullable private String legacy;

    // Annotation with args + field on same line
    @Column(name = "user_name") private String userName;

    // Annotation + method on same line
    @Override public String toString() {
        return oldName;
    }

    // Annotation + method with body on same line
    @Deprecated public int getCount() {
        return count;
    }

    // Annotation with nested parens + field
    @Value("${app.name}") private String appName;

    // Pure annotation with braces (should NOT fall through)
    @ManyToMany(cascade = {})
    private List<String> tags;

    // Normal method
    public String getNickname() {
        return nickname;
    }
}
