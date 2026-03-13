package com.example.webapp.repositories.resultmapper;

import com.example.models.dto.billing.RBD;
import com.example.models.dto.common.Direction;
import com.example.models.dto.common.LegType;
import com.example.webapp.constants.BeanConstants;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.ResultSetExtractor;
import org.springframework.stereotype.Component;

/**
 * Extracts RBD (Raw Billing Data) records from the ResultSet and fills missing cab details.
 *
 * <h3>Why ResultSetExtractor instead of RowMapper?</h3>
 *
 * <p>A duty can have multiple rows (legs) in the RBD table. Within a duty, {@code cab_id} and
 * {@code actual_cab_registration} may be null/empty in some rows but present in others. Since each
 * duty has only one assigned cab, we need to fill missing values from sibling rows. This requires
 * access to the entire ResultSet, which RowMapper (single-row processing) cannot provide.
 *
 * <h3>Data Characteristics</h3>
 *
 * <ul>
 *   <li>{@code cab_id} can be null or 0 (both treated as missing)
 *   <li>{@code actual_cab_registration} can be null or empty string (both treated as missing)
 *   <li>These fields can be independently valid/invalid within the same row
 *   <li>Each duty_id has at most one valid cab_id and one valid actual_cab_registration
 * </ul>
 *
 * <h3>Algorithm</h3>
 *
 * <p>Two-pass approach to fill missing cab details:
 *
 * <ol>
 *   <li><b>First pass:</b> Map rows to RBD objects and collect first valid cab_id and
 *       actual_cab_registration per duty_id into separate maps
 *   <li><b>Second pass:</b> Fill missing cab_id and actual_cab_registration from the maps
 * </ol>
 *
 * <h3>Why not SQL window functions?</h3>
 *
 * <p>While SQL approach (COALESCE + FIRST_VALUE OVER PARTITION BY) would work, it was avoided to:
 *
 * <ul>
 *   <li>Reduce CPU load on Redshift cluster
 *   <li>Keep the query simple and maintainable
 *   <li>Handle the logic in application layer where it's easier to test and debug
 * </ul>
 */
@Slf4j
@Component(BeanConstants.RBD_RESULT_SET_EXTRACTOR_BEAN)
public class RBDResultSetExtractor implements ResultSetExtractor<List<RBD>> {

  /**
   * Extracts RBD records from the ResultSet.
   *
   * <p>Performs two passes:
   *
   * <ol>
   *   <li>Maps rows and collects valid cab details per duty
   *   <li>Fills missing cab_id and actual_cab_registration from collected values
   * </ol>
   *
   * @param rs the ResultSet to extract data from
   * @return list of RBD records with missing cab details filled
   */
  @Override
  public List<RBD> extractData(ResultSet rs) throws SQLException, DataAccessException {
    List<RBD> rbdList = new ArrayList<>();
    Map<Integer, Integer> dutyIdToValidCabId = new HashMap<>();
    Map<Integer, String> dutyIdToValidCabReg = new HashMap<>();

    // First pass: map rows and collect valid cab values per duty
    while (rs.next()) {
      RBD rbd = mapRow(rs);
      rbdList.add(rbd);

      if (isValidCabId(rbd.getCabId())) {
        dutyIdToValidCabId.putIfAbsent(rbd.getDutyId(), rbd.getCabId());
      }
      if (isValidString(rbd.getCabRegistrationNumber())) {
        dutyIdToValidCabReg.putIfAbsent(rbd.getDutyId(), rbd.getCabRegistrationNumber());
      }
    }

    rbdList =
        rbdList.stream()
            .filter(
                rbd ->
                    dutyIdToValidCabId.containsKey(rbd.getDutyId())
                        && dutyIdToValidCabReg.containsKey(rbd.getDutyId()))
            .map(
                rbd -> {
                  if (!isValidCabId(rbd.getCabId())) {
                    rbd.setCabId(dutyIdToValidCabId.get(rbd.getDutyId()));
                  }
                  if (!isValidString(rbd.getCabRegistrationNumber())) {
                    rbd.setCabRegistrationNumber(dutyIdToValidCabReg.get(rbd.getDutyId()));
                  }
                  return rbd;
                })
            .toList();

    return rbdList;
  }

  private RBD mapRow(ResultSet rs) throws SQLException {
    RBD rbd = new RBD();
    rbd.setBusinessUnitId(rs.getString("bunit_id"));
    rbd.setDutyId(rs.getInt("duty_id"));
    rbd.setTripId(rs.getInt("trip_id"));
    rbd.setCabRegistrationNumber(rs.getString("actual_cab_registration"));
    rbd.setCabId(rs.getInt("cab_id"));
    rbd.setDisplayCabId(rs.getString("display_cab_id"));
    rbd.setPlannedEmployeeCount(rs.getInt("planned_emp_cnt"));
    rbd.setTravelledEmployeeCount(rs.getInt("travelled_emp_cnt"));
    rbd.setAdhocEmployeeCount(rs.getInt("adhoc_employee_count"));
    rbd.setLegType(parseEnum(rs.getString("leg_type"), LegType::fromValue));
    rbd.setDirection(parseEnum(rs.getString("direction"), Direction::fromValue));
    rbd.setDutyKm(rs.getDouble("duty_km"));
    rbd.setMarshallRequired(rs.getBoolean("escort"));
    rbd.setTripReferenceKm(rs.getDouble("trip_reference_km"));
    rbd.setAudited(rs.getBoolean("is_audited"));
    rbd.setShiftDateTime(parseTimestamp(rs.getTimestamp("shift_date")));
    rbd.setTripOffice(rs.getString("trip_office"));
    rbd.setAdhoc(rs.getBoolean("is_adhoc"));
    return rbd;
  }

  private <T> T parseEnum(String value, Function<String, T> parser) {
    if (value == null || value.isEmpty()) {
      return null;
    }
    return parser.apply(value);
  }

  private LocalDateTime parseTimestamp(Timestamp timestamp) {
    return timestamp != null ? timestamp.toLocalDateTime() : null;
  }

  private boolean isValidCabId(Integer cabId) {
    return cabId != null && cabId != 0;
  }

  private boolean isValidString(String value) {
    return value != null && !value.isEmpty();
  }
}
