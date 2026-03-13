package com.example;

public enum SimpleDirection {
    NORTH,
    SOUTH,
    EAST,
    WEST;

    public boolean isVertical() {
        return this == NORTH || this == SOUTH;
    }

    public boolean isHorizontal() {
        return this == EAST || this == WEST;
    }
}
