package com.example.webapp.kafka;

import com.mindscapehq.raygun4java.core.RaygunClient;
import com.example.models.dto.kafka.TripData;
import com.example.models.dto.kafka.TripStatus;
import com.example.webapp.constants.APIConstants;
import com.example.webapp.constants.BeanConstants;
import com.example.webapp.repositories.BusinessUnitRepository;
import com.example.webapp.utilities.APIUtilities;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.temporal.ChronoUnit;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.jspecify.annotations.NonNull;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.MicrometerConsumerListener;
import org.springframework.kafka.listener.BatchInterceptor;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.support.ExponentialBackOffWithMaxRetries;
import org.springframework.kafka.support.serializer.JacksonJsonDeserializer;
import tools.jackson.databind.json.JsonMapper;

@Slf4j
@Configuration
@RequiredArgsConstructor
public class TripEndKafkaConsumerConfiguration {

  private final JsonMapper jsonMapper;
  private final MeterRegistry meterRegistry;
  private final BusinessUnitRepository businessUnitRepository;
  private final RaygunClient raygunClient;

  @Value("${spring.kafka.consumer.trip-end.group-id}")
  private String kafkaGroupId;

  @Value(value = "${spring.kafka.bootstrap-servers}")
  private String bootstrapAddress;

  @Bean(name = BeanConstants.TRIP_END_EVENT_KAFKA_LISTENER_CONTAINER_FACTORY)
  public ConcurrentKafkaListenerContainerFactory<String, TripData>
      tripEndEventKafkaListenerContainerFactory() {
    ConcurrentKafkaListenerContainerFactory<String, TripData> factory =
        new ConcurrentKafkaListenerContainerFactory<>();
    factory.setConsumerFactory(tripEndEventConsumerFactory());
    factory.setConcurrency(2);
    factory.setBatchListener(true);
    final var exponentialBackOffWithMaxRetries = new ExponentialBackOffWithMaxRetries(3);
    exponentialBackOffWithMaxRetries.setInitialInterval(
        APIUtilities.convertToMilliseconds(1, ChronoUnit.MINUTES));
    exponentialBackOffWithMaxRetries.setMultiplier(2.0d);
    exponentialBackOffWithMaxRetries.setMaxInterval(
        APIUtilities.convertToMilliseconds(2, ChronoUnit.MINUTES));
    factory.setCommonErrorHandler(
        new DefaultErrorHandler(
            (record, e) -> {
              LOG.error(
                  "Exception while processing trip-end event with key: {} and value {}, error: {}",
                  record.key(),
                  record.value(),
                  e.getMessage(),
                  e);
              sendToRaygun(e, record);
            },
            exponentialBackOffWithMaxRetries));
    factory.setBatchInterceptor(
        new BatchInterceptor<>() {
          @Override
          public ConsumerRecords<String, TripData> intercept(
              @NonNull ConsumerRecords<String, TripData> records,
              @NonNull Consumer<String, TripData> consumer) {
            APIUtilities.getOrCreateTraceId();
            if (!records.isEmpty()) {
              ConsumerRecord<String, TripData> first = records.iterator().next();
              MDC.put(APIConstants.MDC_METHOD_KEY, first.topic());
              MDC.put(APIConstants.MDC_URI_KEY, first.partition() + ":" + first.offset());
            }
            return records;
          }

          @Override
          public void success(
              @NonNull ConsumerRecords<String, TripData> records,
              @NonNull Consumer<String, TripData> consumer) {
            APIUtilities.clearMdc();
          }

          @Override
          public void failure(
              @NonNull ConsumerRecords<String, TripData> records,
              @NonNull Exception exception,
              @NonNull Consumer<String, TripData> consumer) {
            APIUtilities.clearMdc();
          }
        });
    factory.setRecordFilterStrategy(this::filterTripEndEvents);
    factory.getContainerProperties().setMicrometerEnabled(true);
    factory.setContainerCustomizer(
        container -> {
          container.getContainerProperties().setStopContainerWhenFenced(true);
          container.getContainerProperties().setStopImmediate(true);
        });
    return factory;
  }

  private ConsumerFactory<String, TripData> tripEndEventConsumerFactory() {
    Map<String, Object> props = new HashMap<>();
    props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapAddress);
    props.put(ConsumerConfig.GROUP_ID_CONFIG, kafkaGroupId);
    props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100);
    props.put(
        ConsumerConfig.MAX_POLL_INTERVAL_MS_CONFIG,
        (int) APIUtilities.convertToMilliseconds(10, ChronoUnit.MINUTES));
    DefaultKafkaConsumerFactory<String, TripData> consumerFactory =
        new DefaultKafkaConsumerFactory<>(
            props,
            new StringDeserializer(),
            new JacksonJsonDeserializer<>(TripData.class, jsonMapper));
    consumerFactory.addListener(new MicrometerConsumerListener<>(meterRegistry));
    return consumerFactory;
  }

  private boolean filterTripEndEvents(ConsumerRecord<String, TripData> record) {
    TripData tripData = record.value();
    if (tripData == null) {
      return true;
    }
    String businessUnitId = tripData.getBusinessUnitId();
    if (businessUnitId == null
        || !businessUnitRepository.findActiveBusinessUnitIds().contains(businessUnitId)) {
      return true;
    }
    TripStatus status = tripData.getTripStatus();
    if (status == null) {
      return false;
    }
    return !(TripStatus.COMPLETED.equals(status));
  }

  private void sendToRaygun(Exception ex, ConsumerRecord<?, ?> record) {
    try {
      final var customData = new HashMap<String, Object>();
      customData.put("trace_id", APIUtilities.getCurrentTraceId());
      customData.put("source", "kafka-trip-end");
      customData.put("topic", record.topic());
      customData.put("partition", record.partition());
      customData.put("offset", record.offset());
      customData.put("key", record.key());

      final var tags = new HashSet<String>();
      tags.add("kafka");
      tags.add("trip-end");
      tags.add(record.topic());
      raygunClient.send(ex, tags, customData);
    } catch (Exception raygunEx) {
      LOG.error("Failed to send exception to Raygun", raygunEx);
    }
  }
}
