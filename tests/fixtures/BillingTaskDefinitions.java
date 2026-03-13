package com.example.webapp.scheduling.task_definitions;

import com.github.kagkarlsson.scheduler.task.TaskDescriptor;
import com.github.kagkarlsson.scheduler.task.helper.ScheduleAndData;

public final class BillingTaskDefinitions {

  public static final String BILLING_MONITOR_TASK = "billing-monitor";
  public static final String BILLING_CALCULATION_TASK = "billing-calculation";

  public static final TaskDescriptor<ScheduleAndData> BILLING_CALCULATION_DESCRIPTOR =
      TaskDescriptor.of(BILLING_CALCULATION_TASK, ScheduleAndData.class);

  private BillingTaskDefinitions() {
    throw new UnsupportedOperationException("Constant class");
  }
}
