package com.test.dto;

import lombok.Data;

/**
 * 用户订单数量结果DTO
 */
@Data
public class UserOrderCountDTO {
    private Integer userId;
    private String userName;
    private Integer orderCount;
}
