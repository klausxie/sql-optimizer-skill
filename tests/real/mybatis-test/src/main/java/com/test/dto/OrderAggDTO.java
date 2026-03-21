package com.test.dto;

import lombok.Data;
import java.math.BigDecimal;

/**
 * 多函数聚合结果DTO
 */
@Data
public class OrderAggDTO {
    private String status;
    private Integer count;
    private BigDecimal sum;
    private BigDecimal avg;
    private BigDecimal max;
    private BigDecimal min;
}
