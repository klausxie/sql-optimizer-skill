package com.test.dto;

import lombok.Data;
import lombok.experimental.Accessors;
import com.test.entity.Order;
import java.math.BigDecimal;

/**
 * 用户与订单嵌套查询结果DTO
 */
@Data
@Accessors(chain = true)
public class UserOrderNestedDTO {
    private Integer userId;
    private String userName;
    private String userEmail;
    private Long orderId;
    private String orderNo;
    private BigDecimal orderAmount;
    private Order order;
}
