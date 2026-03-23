package com.test.dto;

import lombok.Data;
import lombok.experimental.Accessors;
import java.math.BigDecimal;

/**
 * 订单明细DTO
 */
@Data
@Accessors(chain = true)
public class OrderItemDTO {
    private Long orderId;
    private String orderNo;
    private Long itemId;
    private String itemName;
    private Integer quantity;
    private BigDecimal price;
}
