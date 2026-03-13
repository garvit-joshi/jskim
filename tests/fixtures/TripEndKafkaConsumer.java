package com.example.webapp.kafka.consumers;

import com.example.models.dto.kafka.TripData;
import com.example.webapp.billing.service.KafkaBillingService;
import com.example.webapp.constants.BeanConstants;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class TripEndKafkaConsumer {

  private final KafkaBillingService kafkaBillingService;

  @KafkaListener(
      topics = "trip_refresher",
      containerFactory = BeanConstants.TRIP_END_EVENT_KAFKA_LISTENER_CONTAINER_FACTORY)
  public void processTripEnd(List<ConsumerRecord<String, TripData>> tripEvents) {
    if (tripEvents == null || tripEvents.isEmpty()) {
      return;
    }

    LOG.info("Received {} trip events from Kafka", tripEvents.size());

    List<TripData> tripDataList = tripEvents.stream().map(ConsumerRecord::value).toList();

    if (tripDataList.isEmpty()) {
      LOG.debug("No valid trip events to process");
      return;
    }

    kafkaBillingService.processTripEvents(tripDataList);
  }
}
