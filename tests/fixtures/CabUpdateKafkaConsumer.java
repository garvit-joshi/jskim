package com.example.webapp.kafka.consumers;

import com.example.models.dto.kafka.VMSCabUpdateDTO;
import com.example.webapp.constants.BeanConstants;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class CabUpdateKafkaConsumer {

  @KafkaListener(
      topics = "CAB_UPDATE",
      containerFactory = BeanConstants.CAB_UPDATE_EVENT_KAFKA_LISTENER_CONTAINER_FACTORY)
  public void processCabUpdate(ConsumerRecord<String, VMSCabUpdateDTO> record) {
    final var cabUpdate = record.value();
    LOG.info(
        "Received cab update event for cabId: {} in businessUnitId: {}",
        cabUpdate.getNativeVehicleId(),
        cabUpdate.getBusinessUnitId());
  }
}
