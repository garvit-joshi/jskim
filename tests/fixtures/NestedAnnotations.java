package com.example;

import java.util.*;

// Nested annotation inside another annotation
@ComponentScan(
    basePackages = "com.example",
    excludeFilters = @Filter(type = FilterType.ASSIGNABLE_TYPE, classes = TestConfig.class))
public class NestedAnnotations {

    // Nested annotation on field — single line
    @JoinColumn(name = "user_id", foreignKey = @ForeignKey(name = "FK_USER"))
    private Long userId;

    // Array of nested annotations on field
    @NamedQueries({
        @NamedQuery(name = "findAll", query = "SELECT e FROM Entity e"),
        @NamedQuery(name = "findById", query = "SELECT e FROM Entity e WHERE e.id = :id")
    })
    private String queryHolder;

    // Nested annotation inline with field
    @JoinColumn(name = "order_id", foreignKey = @ForeignKey(name = "FK_ORDER")) private Long orderId;

    // Deeply nested annotation (annotation inside annotation inside annotation)
    @SqlResultSetMapping(
        name = "mapping",
        columns = @ColumnResult(name = "col"),
        entities = @EntityResult(
            entityClass = Object.class,
            fields = @FieldResult(name = "id", column = "ID")))
    private String resultMapping;

    // Nested annotation on method — separate line
    @Cacheable(cacheNames = "users", keyGenerator = @KeyGen(strategy = "hash"))
    public String getUser(String id) {
        return id;
    }

    // Nested annotation inline with method
    @EventListener(condition = @Condition(value = "#event.success")) public void onEvent(Object event) {
        System.out.println(event);
    }

    // Pure nested annotation on its own line (no code after)
    @Mapping(target = "name", qualifiedBy = @Named("trimmer"))
    private String name;

    // Normal method (should still be detected)
    public Long getUserId() {
        return userId;
    }

    // Normal field (should still be detected)
    private int count = 0;
}
