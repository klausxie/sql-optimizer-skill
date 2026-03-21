package com.test.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 日期函数结果DTO
 */
@Data
public class OrderDateDTO {
    private Long orderId;
    private String orderNo;
    private LocalDateTime createdAt;
    private Integer year;
    private Integer month;
    private Integer day;
}
