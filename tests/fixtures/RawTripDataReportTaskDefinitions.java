package com.example.webapp.scheduling.task_definitions;

import com.github.kagkarlsson.scheduler.task.TaskDescriptor;
import java.io.Serial;
import java.io.Serializable;

public final class RawTripDataReportTaskDefinitions {

  public static final String REPORT_GENERATION_TASK = "raw-trip-data-report-generation";

  public static final TaskDescriptor<RawTripDataReportTaskData> REPORT_GENERATION_DESCRIPTOR =
      TaskDescriptor.of(REPORT_GENERATION_TASK, RawTripDataReportTaskData.class);

  public record RawTripDataReportTaskData(Integer reportId) implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
  }

  private RawTripDataReportTaskDefinitions() {
    throw new UnsupportedOperationException("Constant class");
  }
}
