package com.test.dto;

import lombok.Data;
import java.math.BigDecimal;

/**
 * 订单排名结果DTO
 */
@Data
public class OrderRankDTO {
    private Long orderId;
    private String orderNo;
    private BigDecimal amount;
    private Integer rank;
}
