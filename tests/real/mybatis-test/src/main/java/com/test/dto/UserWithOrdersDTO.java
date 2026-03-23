package com.test.dto;

import lombok.Data;
import lombok.experimental.Accessors;
import java.util.List;
import com.test.entity.Order;

/**
 * 用户与订单列表关联查询结果DTO
 */
@Data
@Accessors(chain = true)
public class UserWithOrdersDTO {
    private Integer userId;
    private String userName;
    private List<Order> orders;
}
