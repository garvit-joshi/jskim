package com.example.webapp.kafka;

import com.mindscapehq.raygun4java.core.RaygunClient;
import com.example.models.dto.kafka.VMSCabUpdateDTO;
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
import org.apache.kafka.common.serialization.StringDeserializer;
import org.jspecify.annotations.NonNull;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.MicrometerConsumerListener;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.listener.RecordInterceptor;
import org.springframework.kafka.support.ExponentialBackOffWithMaxRetries;
import org.springframework.kafka.support.serializer.JacksonJsonDeserializer;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

@Slf4j
@Component
@RequiredArgsConstructor
public class CabCreationConsumerConfiguration {

  private final JsonMapper jsonMapper;
  private final MeterRegistry meterRegistry;
  private final BusinessUnitRepository businessUnitRepository;
  private final RaygunClient raygunClient;

  @Value("${spring.kafka.consumer.cab-update.group-id}")
  private String kafkaGroupId;

  @Value(value = "${spring.kafka.bootstrap-servers}")
  private String bootstrapAddress;

  @Bean(name = BeanConstants.CAB_UPDATE_EVENT_KAFKA_LISTENER_CONTAINER_FACTORY)
  public ConcurrentKafkaListenerContainerFactory<String, VMSCabUpdateDTO>
      cabUpdateEventKafkaListenerContainerFactory() {
    ConcurrentKafkaListenerContainerFactory<String, VMSCabUpdateDTO> factory =
        new ConcurrentKafkaListenerContainerFactory<>();
    factory.setConsumerFactory(cabCreationEventConsumerFactory());
    factory.setConcurrency(2);
    ExponentialBackOffWithMaxRetries exponentialBackOffWithMaxRetries =
        new ExponentialBackOffWithMaxRetries(3);
    exponentialBackOffWithMaxRetries.setInitialInterval(
        APIUtilities.convertToMilliseconds(5, ChronoUnit.MINUTES));
    exponentialBackOffWithMaxRetries.setMultiplier(2.0d);
    exponentialBackOffWithMaxRetries.setMaxInterval(
        APIUtilities.convertToMilliseconds(30, ChronoUnit.MINUTES));
    factory.setCommonErrorHandler(
        new DefaultErrorHandler(
            (record, e) -> {
              LOG.error(
                  "Exception while processing cab-creation event with key: {} and value {}, error: {}",
                  record.key(),
                  record.value(),
                  e.getMessage(),
                  e);
              sendToRaygun(e, record);
            },
            exponentialBackOffWithMaxRetries));
    factory.setRecordInterceptor(
        new RecordInterceptor<>() {
          @Override
          public ConsumerRecord<String, VMSCabUpdateDTO> intercept(
              @NonNull ConsumerRecord<String, VMSCabUpdateDTO> record,
              @NonNull Consumer<String, VMSCabUpdateDTO> consumer) {
            APIUtilities.getOrCreateTraceId();
            MDC.put(APIConstants.MDC_METHOD_KEY, record.topic());
            MDC.put(APIConstants.MDC_URI_KEY, record.partition() + ":" + record.offset());
            return record;
          }

          @Override
          public void afterRecord(
              @NonNull ConsumerRecord<String, VMSCabUpdateDTO> record,
              @NonNull Consumer<String, VMSCabUpdateDTO> consumer) {
            APIUtilities.clearMdc();
          }
        });
    factory.setRecordFilterStrategy(this::filterCabCreationEvent);
    factory.getContainerProperties().setMicrometerEnabled(true);
    factory.setContainerCustomizer(
        container -> {
          container.getContainerProperties().setStopContainerWhenFenced(true);
          container.getContainerProperties().setStopImmediate(true);
        });
    return factory;
  }

  private ConsumerFactory<String, VMSCabUpdateDTO> cabCreationEventConsumerFactory() {
    Map<String, Object> props = new HashMap<>();
    props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapAddress);
    props.put(ConsumerConfig.GROUP_ID_CONFIG, kafkaGroupId);
    DefaultKafkaConsumerFactory<String, VMSCabUpdateDTO> consumerFactory =
        new DefaultKafkaConsumerFactory<>(
            props,
            new StringDeserializer(),
            new JacksonJsonDeserializer<>(VMSCabUpdateDTO.class, jsonMapper));
    consumerFactory.addListener(new MicrometerConsumerListener<>(meterRegistry));
    return consumerFactory;
  }

  private boolean filterCabCreationEvent(ConsumerRecord<String, VMSCabUpdateDTO> record) {
    if (record == null) {
      return true;
    }
    final var vmsCabUpdateDTO = record.value();
    if (vmsCabUpdateDTO == null) {
      return true;
    }
    final var businessUnitId = vmsCabUpdateDTO.getBusinessUnitId();
    final var registration = vmsCabUpdateDTO.getRegistration();
    if (businessUnitId == null || registration == null) {
      return true;
    }
    return !businessUnitRepository.findActiveBusinessUnitIds().contains(businessUnitId);
  }

  private void sendToRaygun(Exception ex, ConsumerRecord<?, ?> record) {
    try {
      final var customData = new HashMap<String, Object>();
      customData.put("trace_id", APIUtilities.getCurrentTraceId());
      customData.put("source", "kafka-cab-update");
      customData.put("topic", record.topic());
      customData.put("partition", record.partition());
      customData.put("offset", record.offset());
      customData.put("key", record.key());

      final var tags = new HashSet<String>();
      tags.add("kafka");
      tags.add("cab-update");
      tags.add(record.topic());
      raygunClient.send(ex, tags, customData);
    } catch (Exception raygunEx) {
      LOG.error("Failed to send exception to Raygun", raygunEx);
    }
  }
}
