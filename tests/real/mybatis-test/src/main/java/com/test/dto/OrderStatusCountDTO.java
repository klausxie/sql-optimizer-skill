package com.test.dto;

import lombok.Data;

/**
 * 按状态统计订单数结果DTO
 */
@Data
public class OrderStatusCountDTO {
    private String status;
    private Integer count;
}
