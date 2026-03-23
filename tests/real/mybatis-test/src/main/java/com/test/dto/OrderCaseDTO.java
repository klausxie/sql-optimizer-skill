package com.test.dto;

import lombok.Data;
import java.math.BigDecimal;

/**
 * CASE WHEN 条件表达式结果DTO
 */
@Data
public class OrderCaseDTO {
    private Long orderId;
    private String orderNo;
    private String status;
    private BigDecimal amount;
    private String statusLabel;
}
