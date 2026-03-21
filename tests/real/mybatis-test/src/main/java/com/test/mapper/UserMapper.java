package com.test.mapper;

import com.test.dto.*;
import com.test.entity.User;
import com.test.entity.Order;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import java.util.List;

@Mapper
public interface UserMapper {
    
    // ========== 基础场景测试 ==========
    
    // 场景1: 单个 if 条件
    List<User> testSingleIf(@Param("name") String name);
    
    // 场景2: 2个 if 条件组合
    List<User> testTwoIf(@Param("name") String name, @Param("email") String email);
    
    // 场景3: 3个 if 条件组合
    List<User> testThreeIf(@Param("name") String name, @Param("email") String email, @Param("status") String status);
    
    // 场景4: 4个 if 条件组合
    List<User> testFourIf(@Param("name") String name, @Param("email") String email, 
                          @Param("status") String status, @Param("type") String type);
    
    // 场景5: choose + 2个 when
    List<User> testChooseWhen(@Param("type") String type);
    
    // 场景6: choose + when + otherwise
    List<User> testChooseOtherwise(@Param("type") String type);
    
    // 场景7: where + if
    List<User> testWhereIf(@Param("status") String status);
    
    // 场景8: set + if
    int testSetIf(User user);
    
    // 场景9: foreach (IN 查询)
    List<User> testForeachIn(@Param("ids") List<Integer> ids);
    
    // 场景10: trim
    List<User> testTrim(@Param("name") String name, @Param("status") String status);
    
    // ========== 组合场景测试 ==========
    
    // 场景11: if + choose 嵌套
    List<User> testIfChoose(@Param("status") String status, @Param("type") String type);
    
    // 场景12: where + 多个 if
    List<User> testWhereMultipleIf(@Param("name") String name, @Param("email") String email, 
                                   @Param("status") String status, @Param("type") String type);
    
    // 场景13: choose + if x2
    List<User> testChooseMultipleIf(@Param("type") String type, @Param("status") String status);
    
    // 场景14: if + foreach 嵌套
    List<User> testIfForeach(@Param("ids") List<Integer> ids, @Param("status") String status);
    
    // 场景15: where + choose + when
    List<User> testWhereChooseWhen(@Param("status") String status, @Param("type") String type);
    
    // 场景16: choose 内嵌多个 if
    List<User> testChooseWithMultipleIf(@Param("type") String type, @Param("status") String status);
    
    // ========== 复杂场景测试 ==========
    
    // 场景17: 5个 if 条件 (32分支)
    List<User> testFiveIf(@Param("name") String name, @Param("email") String email,
                          @Param("status") String status, @Param("type") String type);
    
    // 场景18: choose 嵌套 choose
    List<User> testChooseNestedChoose(@Param("status") String status, @Param("type") String type);
    
    // 场景19: 复杂多条件组合
    List<User> testComplexConditions(@Param("name") String name, @Param("email") String email,
                                     @Param("status") String status, @Param("type") String type);
    
    // 场景20: 动态排序
    List<User> testDynamicOrderBy(@Param("name") String name, @Param("orderField") String orderField, @Param("orderType") String orderType);
    
    // ========== 高级场景测试 ==========
    
    // 场景21: bind + if 动态绑定
    List<User> testBindIf(@Param("name") String name, @Param("status") String status);
    
    // 场景22: trim前后缀精确控制
    List<User> testTrimPrefixSuffix(@Param("name") String name, @Param("email") String email);
    
    // 场景23: foreach批量插入
    int testForeachInsert(@Param("users") List<User> users);
    
    // 场景24: 动态列名
    List<User> testDynamicColumns(@Param("includeName") boolean includeName, @Param("includeEmail") boolean includeEmail,
                                  @Param("includeStatus") boolean includeStatus, @Param("includeType") boolean includeType,
                                  @Param("name") String name);
    
    // 场景25: 复杂choose - 3层嵌套
    List<User> testChooseTripleNested(@Param("status") String status, @Param("type") String type, @Param("name") String name);
    
    // 场景26: set + if 多字段更新
    int testSetMultipleIf(User user);
    
    // 场景27: if test 多条件逻辑运算
    List<User> testIfMultiCondition(@Param("name") String name, @Param("email") String email, @Param("status") String status);
    
    // 场景28: foreach + choose
    List<User> testForeachChoose(@Param("ids") List<Integer> ids, @Param("status") String status);
    
    // 场景29: 复杂trim - UPDATE动态
    int testTrimUpdate(User user);
    
    // 场景30: 多层if + foreach组合
    List<User> testIfForeachComplex(@Param("status") String status, @Param("types") List<String> types,
                                     @Param("name") String name, @Param("ids") List<Integer> ids);
    
    // ========== SQL 片段引用测试 (场景31-36) ==========
    
    // 场景31: include 引用基础列
    User testIncludeBaseColumns(@Param("id") Integer id);
    
    // 场景32: include 引用带 if 的片段
    List<User> testIncludeCondition(@Param("status") String status, @Param("type") String type);
    
    // 场景33: 多个 include 组合
    List<User> testMultipleInclude(@Param("name") String name, @Param("email") String email,
                                   @Param("status") String status);
    
    // 场景34: include 引用复杂嵌套片段
    List<User> testIncludeComplex(@Param("status") String status, @Param("type") String type,
                                  @Param("name") String name);
    
    // 场景35: include 嵌套在 if 中
    List<User> testIncludeInIf(@Param("useStatusFilter") boolean useStatusFilter,
                               @Param("useTypeFilter") boolean useTypeFilter,
                               @Param("status") String status,
                               @Param("type") String type);
    
    // 场景36: include 嵌套在 choose 中
    List<User> testIncludeInChoose(@Param("filterMode") String filterMode,
                                   @Param("status") String status, @Param("type") String type,
                                   @Param("name") String name, @Param("email") String email);
    
    // ========== 高级 bind 测试 (场景37-38) ==========
    
    // 场景37: 多个 bind 链式使用
    List<User> testMultipleBind(@Param("name") String name, @Param("email") String email,
                                @Param("status") String status);
    
    // 场景38: bind 与 include 组合
    List<User> testBindWithInclude(@Param("status") String status);
    
    // ========== 边界情况测试 (场景39-45) ==========
    
    // 场景39: 空条件 if
    List<User> testEmptyIf();
    
    // 场景40: 只有 otherwise 的 choose
    List<User> testOnlyOtherwise();
    
    // 场景41: 多层 trim 嵌套
    List<User> testNestedTrim(@Param("name") String name, @Param("email") String email);
    
    // 场景42: foreach 嵌套 foreach
    List<User> testNestedForeach(@Param("statusList") List<String> statusList);
    
    // 场景43: include 传递参数
    List<User> testIncludeWithProperty(@Param("status") String status);
    
    // 场景44: 超长条件组合 (压力测试) - 映射到真实列名
    List<User> testLongConditions(@Param("name") String c1, @Param("email") String c2,
                                  @Param("c3") String c3, @Param("status") String c4,
                                  @Param("c5") String c5, @Param("c6") String c6,
                                  @Param("type") String c7, @Param("c8") String c8);
    
    // 场景45: 完整 CRUD 操作组合测试
    int testInsertWithSelectKey(@Param("users") List<User> users);
    
    // ========== 多表关联测试 (场景46-55) ==========
    
    // 场景46: 内连接 - 用户与订单
    List<UserOrderDTO> testInnerJoin();
    
    // 场景47: 左外连接 - 用户与订单
    List<UserOrderDTO> testLeftJoin();
    
    // 场景48: 多表连接 - 用户、订单、订单明细
    List<UserOrderItemDTO> testMultiTableJoin(@Param("userId") Integer userId);
    
    // 场景49: 动态 join 条件
    List<UserOrderDTO> testDynamicJoin(@Param("userId") Integer userId, @Param("status") String status);
    
    // 场景50: 子查询 - IN 查询用户订单
    List<User> testSubqueryIn(@Param("userIds") List<Integer> userIds);
    
    // 场景51: 子查询 - EXISTS 检查用户是否有订单
    List<User> testSubqueryExists(@Param("status") String status);
    
    // 场景52: 标量子查询 - 获取用户订单总数
    List<UserOrderCountDTO> testScalarSubquery();
    
    // 场景53: 动态多表关联
    List<UserOrderDTO> testDynamicMultiTableJoin(@Param("userId") Integer userId, 
                                                  @Param("orderStatus") String orderStatus);
    
    // 场景54: UNION 查询
    List<User> testUnion(@Param("type") String type);
    
    // 场景55: 多层嵌套子查询
    List<UserOrderDTO> testNestedSubquery(@Param("minAmount") Double minAmount);
    
    // ========== 函数/聚合测试 (场景56-70) ==========
    
    // 场景56: COUNT 聚合
    int testCountAll();
    
    // 场景57: COUNT 条件聚合
    int testCountByStatus(@Param("status") String status);
    
    // 场景58: SUM 聚合
    Double testSumAmount();
    
    // 场景59: AVG 聚合
    Double testAvgAmount();
    
    // 场景60: MAX/MIN 聚合
    OrderAmountDTO testMaxMinAmount();
    
    // 场景61: 分组聚合 - GROUP BY
    List<OrderStatusCountDTO> testGroupBy();
    
    // 场景62: 分组聚合 - 多字段分组
    List<OrderUserStatusDTO> testMultiGroupBy(@Param("userId") Integer userId);
    
    // 场景63: HAVING 过滤
    List<OrderStatusCountDTO> testGroupByHaving(@Param("minCount") Integer minCount);
    
    // 场景64: CASE WHEN 条件表达式
    List<OrderCaseDTO> testCaseWhen();
    
    // 场景65: DATE 函数
    List<OrderDateDTO> testDateFunction(@Param("year") Integer year);
    
    // 场景66: 字符串函数 - CONCAT
    List<User> testStringConcat(@Param("prefix") String prefix);
    
    // 场景67: 字符串函数 - SUBSTRING
    List<User> testStringSubstring(@Param("pattern") String pattern);
    
    // 场景68: 条件聚合 - SUM CASE WHEN
    Double testConditionalSum(@Param("status") String status);
    
    // 场景69: 多函数组合
    List<OrderAggDTO> testMultiAggFunction();
    
    // 场景70: 窗口函数模拟 - 订单排名
    List<OrderRankDTO> testOrderRank();
    
    // ========== 分页测试 (场景71-75) ==========
    
    // 场景71: LIMIT 分页
    List<Order> testLimit(@Param("limit") Integer limit);
    
    // 场景72: LIMIT + OFFSET 分页
    List<Order> testLimitOffset(@Param("limit") Integer limit, @Param("offset") Integer offset);
    
    // 场景73: 动态分页
    List<Order> testDynamicPagination(@Param("pageSize") Integer pageSize, @Param("offset") Integer offset);
    
    // ========== DISTINCT 测试 (场景76-78) ==========
    
    // 场景76: DISTINCT 去重
    List<String> testDistinctStatus();
    
    // 场景77: DISTINCT 多字段
    List<User> testDistinctMultipleFields();
    
    // ========== 数据库特有语法 (场景79-85) ==========
    
    // 场景79: MySQL INSERT...ON DUPLICATE KEY UPDATE
    int testInsertOnDuplicateKeyUpdate(User user);
    
    // 场景80: PostgreSQL RETURNING (映射为普通查询测试)
    List<Order> testReturningSyntax();
    
    // 场景81: 动态条件 + DISTINCT + 分页组合
    List<String> testDistinctWithCondition(@Param("status") String status);
    
    // 场景82: 聚合 + DISTINCT
    int testCountDistinct(@Param("status") String status);
    
    // 场景83: 多字段排序 + 分页
    List<Order> testOrderByMultipleWithPagination(@Param("pageSize") Integer pageSize, @Param("offset") Integer offset);
    
    // 场景84: 复杂 WHERE + GROUP BY + HAVING + ORDER BY + LIMIT
    List<OrderStatusCountDTO> testComplexAggregation(@Param("minAmount") Double minAmount);
    
    // 场景85: UNION + LIMIT
    List<User> testUnionWithLimit(@Param("type") String type, @Param("limit") Integer limit);
    
    // ========== 场景86-95: 跨文件 SQL 片段引用测试 ==========
    
    // 场景86: 直接跨文件引用 CommonMapper 片段
    List<User> testCrossFileInclude(@Param("status") String status);
    
    // 场景87: 跨文件引用 + 本地 if 条件
    List<User> testCrossFileIncludeWithIf(@Param("name") String name, @Param("status") String status);
    
    // 场景88: 本地 SQL 片段引用跨文件片段
    List<User> testLocalFragmentWithCrossFile(@Param("type") String type, @Param("status") String status,
                                               @Param("startDate") String startDate, @Param("endDate") String endDate);
    
    // 场景89: choose 内跨文件引用
    List<User> testCrossFileInChoose(@Param("filterMode") String filterMode, @Param("status") String status,
                                      @Param("startDate") String startDate, @Param("endDate") String endDate);
    
    // 场景90: foreach + 跨文件引用组合
    List<User> testCrossFileWithForeach(@Param("ids") List<Integer> ids, @Param("status") String status,
                                         @Param("pageSize") Integer pageSize, @Param("offset") Integer offset);
    
    // 场景91: 多次跨文件引用同一片段
    List<User> testMultipleCrossFileInclude(@Param("status") String status);
    
    // 场景92: 跨文件引用带嵌套 choose 的片段
    List<User> testCrossFileNestedChoose(@Param("useComplex") Boolean useComplex, @Param("status") String status,
                                         @Param("type") String type);
    
    // 场景93: trim 内跨文件引用
    List<User> testCrossFileInTrim(@Param("status") String status, @Param("type") String type);
    
    // 场景94: set 内跨文件引用
    int testCrossFileInSet(@Param("status") String status, @Param("type") String type);
    
    // 场景95: 三层引用链 - UserMapper -> 本地片段 -> CommonMapper
    List<User> testChainedCrossFileInclude(@Param("status") String status, @Param("type") String type);
    
    // ========== selectKey 测试 (S1-S4) ==========
    
    // 场景 S1: Oracle Sequence (order="BEFORE")
    int testSelectKeyOracle(User user);
    
    // 场景 S2: PostgreSQL Sequence
    int testSelectKeyPostgres(User user);
    
    // 场景 S3: MySQL AUTO_INCREMENT (order="AFTER")
    int testSelectKeyMysql(User user);
    
    // 场景 S4: UUID/随机数生成
    int testSelectKeyUuid(User user);
    
    // ========== resultMap 嵌套测试 (R1-R6) ==========
    
    // 场景 R1: resultMap + association (一对一)
    List<UserOrderNestedDTO> testResultMapAssociation();
    
    // 场景 R2: resultMap + collection (一对多)
    List<UserWithOrdersDTO> testResultMapCollection();
    
    // 场景 R3: resultMap 缺少 id (诊断场景)
    List<User> testResultMapNoId();
    
    // 场景 R4: Nested Select (N+1 问题诊断)
    List<UserWithOrdersDTO> testNestedSelectN1();
    
    // 场景 R5: Nested Result (正确方式)
    List<UserWithOrdersDTO> testNestedResult();
    
    // 场景 R6: discriminator 动态映射
    List<User> testDiscriminator();
    
    // ========== 子查询诊断测试 (Q1-Q3) ==========
    
    // 场景 Q1: 关联子查询 (Correlated Subquery)
    List<User> testCorrelatedSubquery();
    
    // 场景 Q2: 标量子查询 (Scalar Subquery)
    List<UserOrderCountDTO> testScalarSubqueryNew();
    
    // 场景 Q3: 多层嵌套子查询
    List<User> testNestedSubqueryComplex();
}
