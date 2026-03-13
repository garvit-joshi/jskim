package com.example.config;

import com.example.clients.NotificationClient;
import com.example.services.AuditService;
import com.example.services.CacheService;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.MeterRegistry;
import okhttp3.OkHttpClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

@Configuration
public class AppConfiguration {

  private static final int POOL_SIZE = 10;
  private static final String THREAD_PREFIX = "app-scheduler-";

  @Bean
  public ObjectMapper objectMapper() {
    return new ObjectMapper()
        .findAndRegisterModules();
  }

  @Bean
  public OkHttpClient httpClient() {
    return new OkHttpClient.Builder()
        .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
        .readTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
        .build();
  }

  @Bean
  public TaskScheduler taskScheduler() {
    ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
    scheduler.setPoolSize(POOL_SIZE);
    scheduler.setThreadNamePrefix(THREAD_PREFIX);
    return scheduler;
  }

  @Bean
  public NotificationClient notificationClient(OkHttpClient httpClient, ObjectMapper mapper) {
    return new NotificationClient(httpClient, mapper);
  }

  @Bean
  public AuditService auditService(ObjectMapper mapper) {
    return new AuditService(mapper);
  }

  @Bean
  public CacheService cacheService(MeterRegistry meterRegistry) {
    return new CacheService(meterRegistry);
  }

  // Non-@Bean method — should NOT appear in producers
  private void logStartup() {
    System.out.println("AppConfiguration initialized");
  }
}
