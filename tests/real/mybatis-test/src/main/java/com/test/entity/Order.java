package com.test.entity;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class Order {
    private Long id;
    private Long userId;
    private String orderNo;
    private BigDecimal amount;
    private String status;
    private String orderType;
    private LocalDateTime createdAt;
}
