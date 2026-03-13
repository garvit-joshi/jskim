package com.example.webapp.billing.calculation;

import com.example.models.dto.billing.ContractConfiguration;
import com.example.models.dto.billing.TripBillingInput;
import com.example.models.dto.billing.TripBillingResult;
import java.math.BigDecimal;

public interface BillingCalculator {

  TripBillingResult calculate(TripBillingInput input);

  /**
   * Checks if the trip is a single escort trip that should be billed at zero cost.
   *
   * <p>A trip is a single escort trip when:
   *
   * <ul>
   *   <li>The contract's {@code considerSingleEscortTrips} is {@code false}
   *   <li>The trip is adhoc
   *   <li>Escort (marshall) is required
   *   <li>Both planned and travelled employee counts are &le; 1
   * </ul>
   */
  default boolean isSingleEscortTrip(TripBillingInput input) {
    ContractConfiguration contractConfiguration = input.contractConfig();
    if (contractConfiguration == null
        || Boolean.TRUE.equals(contractConfiguration.considerSingleEscortTrips())) {
      return false;
    }

    return Boolean.TRUE.equals(input.adhoc())
        && Boolean.TRUE.equals(input.marshallRequired())
        && input.plannedEmployeeCount() <= 1
        && input.travelledEmployeeCount() <= 1;
  }

  default TripBillingResult zeroCostResult(TripBillingInput input) {
    ContractConfiguration config = input.contractConfig();
    return new TripBillingResult(
        input.businessUnitId(),
        input.tripId(),
        input.dutyId(),
        input.cabId(),
        input.cabRegistrationNumber(),
        input.shiftDateTime(),
        input.tripKm(),
        input.direction(),
        config != null ? config.contractName() : null,
        config != null ? config.contractId() : null,
        BigDecimal.ZERO,
        BigDecimal.ZERO,
        BigDecimal.ZERO);
  }
}
