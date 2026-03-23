package com.test.dto;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 用户与订单关联查询结果DTO
 */
@Data
public class UserOrderDTO {
    private Integer userId;
    private String userName;
    private String userEmail;
    private Long orderId;
    private String orderNo;
    private String orderStatus;
    private BigDecimal amount;
    private LocalDateTime createdAt;
}
