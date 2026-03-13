package com.example.webapp.repositories.resultmapper;

import com.example.models.dto.reports.RawTripRow;
import com.example.webapp.constants.BeanConstants;
import com.example.webapp.utilities.VehicleUtilities;
import java.sql.ResultSet;
import java.sql.SQLException;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Component;

@Component(BeanConstants.RAW_TRIP_ROW_MAPPER_BEAN)
public class RawTripRowMapper implements RowMapper<RawTripRow> {

  @Override
  public RawTripRow mapRow(ResultSet rs, int rowNum) throws SQLException {
    return new RawTripRow(
        rs.getInt("trip_id"),
        rs.getString("shift"),
        rs.getString("bunit_id"),
        rs.getString("actual_cabtype"),
        rs.getObject("actual_cab_capacity", Integer.class),
        rs.getString("vendor_id"),
        rs.getObject("actual_escort", Boolean.class),
        rs.getString("trip_direction"),
        rs.getObject("plannedemployee_cnt", Integer.class),
        rs.getObject("actualemployee_cnt", Integer.class),
        rs.getString("office"),
        rs.getObject("planned_km", Double.class),
        rs.getObject("trip_reference_km", Double.class),
        rs.getObject("traveled_km", Double.class),
        rs.getObject("trip_approved_km", Double.class),
        rs.getDate("trip_date") != null ? rs.getDate("trip_date").toLocalDate() : null,
        rs.getString("trip_state_text"),
        rs.getString("trip_status_text"),
        VehicleUtilities.formatVehicleRegistrationNumber(rs.getString("actual_cab_registration")),
        VehicleUtilities.formatVehicleRegistrationNumber(rs.getString("planned_cab_registration")),
        rs.getObject("is_cab_virtual", Boolean.class),
        rs.getString("subvendor_name"),
        null);
  }
}
