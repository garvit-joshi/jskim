package com.example;

import java.util.*;
import java.util.function.*;
import jakarta.persistence.*;

@Entity
@Data
public class ComplexMixed {
    private static final String SQL = """
        SELECT *
        FROM users
        WHERE status = 'ACTIVE'
        AND count > {threshold}
        """;

    private Comparator<String> comp = Comparator.comparing(String::length);

    private final Map<String, Object> defaults = new HashMap<>() {{
        put("timeout", 30);
        put("retries", 3);
    }};

    @Autowired
    private UserService userService;

    @Column(name = "user_name")
    private String userName;

    @ManyToMany(cascade = {CascadeType.PERSIST,
        CascadeType.MERGE})
    private List<Role> roles;

    public ComplexMixed(UserService userService) {
        this.userService = userService;
    }

    public List<String> findUsers(String query) {
        return userService.search(query);
    }

    private void validate(String input) {
        if (input == null) {
            throw new IllegalArgumentException("null input");
        }
    }
}
