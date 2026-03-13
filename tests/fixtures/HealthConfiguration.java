package com.example.webapp.configurations;

import com.example.webapp.constants.BeanConstants;
import javax.sql.DataSource;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.jdbc.health.DataSourceHealthIndicator;
import org.springframework.boot.jdbc.metadata.DataSourcePoolMetadataProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@RequiredArgsConstructor
public class HealthConfiguration {

  private final DataSourcePoolMetadataProvider poolMetadataProvider;

  /**
   * Registers a health indicator for only the Postgres datasource. The Redshift datasource is
   * intentionally excluded because its connection pool is too small (max 1) to spare a connection
   * for the validation query every time Kubernetes pings the health endpoint in production.
   */
  @Bean
  public DataSourceHealthIndicator dbHealthIndicator(
      @Qualifier(BeanConstants.POSTGRES_DATA_SOURCE) DataSource dataSource) {
    final var validationQuery =
        poolMetadataProvider.getDataSourcePoolMetadata(dataSource).getValidationQuery();
    return new DataSourceHealthIndicator(dataSource, validationQuery);
  }
}
