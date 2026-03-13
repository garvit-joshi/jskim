package com.example.services;

import com.example.repositories.OrderRepository;
import com.example.repositories.PaymentRepository;
import com.example.clients.NotificationClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class StaticFieldService {

  // Static final constants — should NOT appear as bean dependencies
  private static final String SERVICE_NAME = "OrderService";
  private static final int MAX_RETRIES = 3;
  private static final long TIMEOUT_MS = 5000L;
  private static final String BASE_URL = "https://api.example.com";

  // Static non-final — also should NOT appear as bean dependencies
  private static String cachedToken;
  private static int requestCount;

  // Final instance fields — SHOULD appear as bean dependencies (constructor-injected)
  private final OrderRepository orderRepository;
  private final PaymentRepository paymentRepository;
  private final NotificationClient notificationClient;

  // Non-final instance field — should NOT appear (not injected via constructor)
  private String lastOrderId;

  public void processOrder(String orderId) {
    LOG.info("{}: Processing order {}", SERVICE_NAME, orderId);
    lastOrderId = orderId;
  }

  public void retryOrder(String orderId) {
    for (int i = 0; i < MAX_RETRIES; i++) {
      LOG.info("Retry {}/{} for order {}", i + 1, MAX_RETRIES, orderId);
    }
  }
}
