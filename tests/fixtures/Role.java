package com.example.auth.enums;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

public enum Role {

    WORKSPACE_MANAGER("WORKSPACE_MANAGER"),
    MSU("MSU"),
    employee("employee"),
    hr_manager("hr_manager"),
    HR_MANAGER("HR MANAGER"),
    admin("admin"),
    Guard("Guard"),
    team_manager("team_manager"),
    OFFICE_ADMIN("OFFICE ADMIN"),
    VISITOR("visitor"),
    GLOBAL_ADMIN("GLOBAL ADMIN"),
    TEAM_MANAGER("TEAM MANAGER");

  private static final Map<String, Role> LOOKUP_MAP;

  static {
    LOOKUP_MAP = new HashMap<>();
    for (Role role : Role.values()) {
      LOOKUP_MAP.put(role.getValue(), role);
    }

  }

  private String value;
  private int id;

  private Role(String role) {
    this.value = role;
  }

  public String getValue() {
    return value;
  }

  public int getRoleId() {
    return id;
  }

  @Override
  public String toString() {
    return "Role{" + "value='" + value + '\'' + '}';
  }

  public String value() {
    return value;
  }

  public static Role getRole(String value) {
    return LOOKUP_MAP.get(value);
  }

  public static String[] allValuesExceptGuardAndEmployee() {
    Role[] values = Role.values();
    return Arrays.stream(values).filter(role -> !role.equals(Role.employee) && !role.equals(Role.Guard))
        .map(Role::getValue).toArray(String[]::new);
  }

}
