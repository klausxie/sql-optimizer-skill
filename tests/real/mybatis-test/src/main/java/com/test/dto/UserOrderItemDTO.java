package com.test.dto;

import lombok.Data;
import java.math.BigDecimal;

/**
 * 用户、订单和订单明细关联查询结果DTO
 */
@Data
public class UserOrderItemDTO {
    private Integer userId;
    private String userName;
    private Long orderId;
    private String orderNo;
    private Long itemId;
    private Long productId;
    private String productName;
    private Integer quantity;
    private BigDecimal price;
}
