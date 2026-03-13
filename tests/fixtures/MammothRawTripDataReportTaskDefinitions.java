package com.example.webapp.scheduling.task_definitions;

import com.github.kagkarlsson.scheduler.task.TaskDescriptor;
import java.io.Serial;
import java.io.Serializable;

public final class MammothRawTripDataReportTaskDefinitions {

  public static final String REPORT_GENERATION_TASK = "mammoth-raw-trip-data-report-generation";

  public static final TaskDescriptor<MammothRawTripDataReportTaskData>
      REPORT_GENERATION_DESCRIPTOR =
          TaskDescriptor.of(REPORT_GENERATION_TASK, MammothRawTripDataReportTaskData.class);

  public record MammothRawTripDataReportTaskData(Integer reportId) implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
  }

  private MammothRawTripDataReportTaskDefinitions() {
    throw new UnsupportedOperationException("Constant class");
  }
}
