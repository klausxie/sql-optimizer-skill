package com.test.dto;

import lombok.Data;

/**
 * 按用户和状态统计订单数结果DTO
 */
@Data
public class OrderUserStatusDTO {
    private Long userId;
    private String status;
    private Integer count;
}
