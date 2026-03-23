package com.test.mapper;

import com.test.entity.Order;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 订单 Mapper - 展示跨文件 SQL 片段引用
 */
@Mapper
public interface OrderMapper {
    
    /**
     * 使用跨文件 CommonMapper 片段的查询
     */
    List<Order> findOrdersWithCommon(@Param("status") String status,
                                      @Param("orderStatus") String orderStatus,
                                      @Param("startDate") String startDate,
                                      @Param("endDate") String endDate,
                                      @Param("pageSize") Integer pageSize,
                                      @Param("offset") Integer offset);
    
    /**
     * if 条件内跨文件引用
     */
    List<Order> findOrdersConditional(@Param("useCommonCondition") Boolean useCommonCondition,
                                      @Param("orderStatus") String orderStatus);
    
    /**
     * choose 内跨文件引用
     */
    List<Order> findOrdersByMode(@Param("mode") String mode,
                                  @Param("status") String status,
                                  @Param("startDate") String startDate,
                                  @Param("endDate") String endDate);
    
    /**
     * 复杂嵌套 - 本地 if 嵌套跨文件
     */
    List<Order> findOrdersComplex(@Param("filterEnabled") Boolean filterEnabled,
                                  @Param("status") String status,
                                  @Param("ids") List<Integer> ids);
}
