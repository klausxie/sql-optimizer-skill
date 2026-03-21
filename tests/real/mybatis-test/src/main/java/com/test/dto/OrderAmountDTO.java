package com.test.dto;

import lombok.Data;
import java.math.BigDecimal;

/**
 * 订单金额聚合结果DTO
 */
@Data
public class OrderAmountDTO {
    private BigDecimal maxAmount;
    private BigDecimal minAmount;
}
