package com.example.webapp.proxies;

import com.mindscapehq.raygun4java.core.RaygunClient;
import com.example.AppBuildUtils;
import com.example.models.dto.common.LocalityDTO;
import com.example.models.dto.common.ShiftDTO;
import com.example.models.exceptions.APIException;
import com.example.webapp.properties.ServiceProperties;
import com.example.webapp.utilities.APIUtilities;
import java.io.IOException;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import org.springframework.stereotype.Component;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

@Slf4j
@Component
@RequiredArgsConstructor
public class ScheduleServiceProxy {

  private static final String SERVICE_NAME = "ScheduleService";

  private final JsonMapper jsonMapper;
  private final OkHttpClient okHttpClient;
  private final ServiceProperties serviceProperty;
  private final RaygunClient raygunClient;

  public List<LocalityDTO> fetchOfficesForBusinessUnitId(String businessUnitId)
      throws APIException {
    LOG.info("Fetching offices for businessUnitId: {}", businessUnitId);

    String url =
        APIUtilities.cleanUrl(
            String.format("%s/ets/apis/office", AppBuildUtils.getUrlOfBuid(businessUnitId)));

    Request request = new Request.Builder().url(url).get().build();

    try (final var response = okHttpClient.newCall(request).execute()) {
      if (!response.isSuccessful()) {
        LOG.error(
            "Failed to fetch offices for businessUnitId: {}. Status code: {}",
            businessUnitId,
            response.code());
        throw new APIException(
            String.format(
                "Fetching offices for %s failed. HTTP Status: %d",
                businessUnitId, response.code()));
      }

      String responseBody = response.body().string();
      return jsonMapper.readValue(responseBody, new TypeReference<>() {});
    } catch (IOException e) {
      LOG.error("Error fetching offices for businessUnitId: {}", businessUnitId, e);
      sendToRaygun(e, url);
      throw new APIException(String.format("Fetching Data of %s Office Failed", businessUnitId), e);
    }
  }

  public List<ShiftDTO> fetchShiftsForBusinessUnitId(String businessUnitId) {
    LOG.info("Fetching shifts for businessUnitId: {}", businessUnitId);

    String url =
        APIUtilities.cleanUrl(
            String.format(
                "%s/v2/shifts/v2?businessUnitId=%s",
                serviceProperty.scheduleServiceUrl(), businessUnitId));

    Request request = new Request.Builder().url(url).get().build();

    try (final var response = okHttpClient.newCall(request).execute()) {
      if (!response.isSuccessful()) {
        LOG.error(
            "Failed to fetch shifts for businessUnitId: {}. Status code: {}",
            businessUnitId,
            response.code());
        return Collections.emptyList();
      }

      String responseBody = response.body().string();
      if (responseBody.isEmpty()) {
        LOG.warn("Empty response body received for shifts. businessUnitId: {}", businessUnitId);
        return Collections.emptyList();
      }
      return jsonMapper.readValue(responseBody, new TypeReference<>() {});
    } catch (IOException e) {
      LOG.error("Error fetching shifts for businessUnitId: {}", businessUnitId, e);
      sendToRaygun(e, url);
      return Collections.emptyList();
    }
  }

  private void sendToRaygun(Exception ex, String url) {
    try {
      final var tags = new HashSet<String>();
      tags.add(SERVICE_NAME);
      tags.add(serviceProperty.scheduleServiceUrl());
      tags.add(url);
      tags.add(APIUtilities.getCurrentTraceId());

      final var customData = new HashMap<String, Object>();
      customData.put("trace_id", APIUtilities.getCurrentTraceId());

      raygunClient.send(ex, tags, customData);
    } catch (Exception raygunEx) {
      LOG.error("Failed to send exception to Raygun", raygunEx);
    }
  }
}
