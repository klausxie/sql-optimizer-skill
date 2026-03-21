package com.test;

import com.test.dto.*;
import com.test.mapper.UserMapper;
import com.test.entity.User;
import com.test.entity.Order;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
public class MyBatisBranchTest {
    
    @Autowired
    private UserMapper userMapper;
    
    // ========== 基础场景测试 ==========
    
    @Test
    public void testSingleIf() {
        List<User> result = userMapper.testSingleIf("张三");
        assertNotNull(result);
        System.out.println("场景1 - 单个if: " + result.size() + " 结果");
    }
    
    @Test
    public void testTwoIf() {
        List<User> result = userMapper.testTwoIf("张三", "zhangsan@example.com");
        assertNotNull(result);
        System.out.println("场景2 - 2个if: " + result.size() + " 结果");
    }
    
    @Test
    public void testThreeIf() {
        List<User> result = userMapper.testThreeIf("张三", "zhangsan@example.com", "1");
        assertNotNull(result);
        System.out.println("场景3 - 3个if: " + result.size() + " 结果");
    }
    
    @Test
    public void testFourIf() {
        List<User> result = userMapper.testFourIf("张三", "zhangsan@example.com", "1", "VIP");
        assertNotNull(result);
        System.out.println("场景4 - 4个if: " + result.size() + " 结果");
    }
    
    @Test
    public void testChooseWhen() {
        List<User> result = userMapper.testChooseWhen("VIP");
        assertNotNull(result);
        System.out.println("场景5 - choose+when: " + result.size() + " 结果");
    }
    
    @Test
    public void testChooseOtherwise() {
        List<User> result = userMapper.testChooseOtherwise("VIP");
        assertNotNull(result);
        System.out.println("场景6 - choose+otherwise: " + result.size() + " 结果");
    }
    
    @Test
    public void testWhereIf() {
        List<User> result = userMapper.testWhereIf("1");
        assertNotNull(result);
        System.out.println("场景7 - where+if: " + result.size() + " 结果");
    }
    
    @Test
    public void testSetIf() {
        User user = new User();
        user.setId(1);
        user.setName("UpdatedUser");
        user.setEmail("updated@example.com");
        int result = userMapper.testSetIf(user);
        System.out.println("场景8 - set+if: " + result + " 条");
    }
    
    @Test
    public void testForeachIn() {
        List<User> result = userMapper.testForeachIn(Arrays.asList(1, 2, 3));
        assertNotNull(result);
        System.out.println("场景9 - foreach: " + result.size() + " 结果");
    }
    
    @Test
    public void testTrim() {
        List<User> result = userMapper.testTrim("张三", "1");
        assertNotNull(result);
        System.out.println("场景10 - trim: " + result.size() + " 结果");
    }
    
    // ========== 组合场景测试 ==========
    
    @Test
    public void testIfChoose() {
        List<User> result = userMapper.testIfChoose("1", "VIP");
        assertNotNull(result);
        System.out.println("场景11 - if+choose: " + result.size() + " 结果");
    }
    
    @Test
    public void testWhereMultipleIf() {
        List<User> result = userMapper.testWhereMultipleIf("张", "zhang", "1", "VIP");
        assertNotNull(result);
        System.out.println("场景12 - where+多if: " + result.size() + " 结果");
    }
    
    @Test
    public void testChooseMultipleIf() {
        List<User> result = userMapper.testChooseMultipleIf("VIP", "1");
        assertNotNull(result);
        System.out.println("场景13 - choose+多if: " + result.size() + " 结果");
    }
    
    @Test
    public void testIfForeach() {
        List<User> result = userMapper.testIfForeach(Arrays.asList(1, 2), "1");
        assertNotNull(result);
        System.out.println("场景14 - if+foreach: " + result.size() + " 结果");
    }
    
    @Test
    public void testWhereChooseWhen() {
        List<User> result = userMapper.testWhereChooseWhen("1", "VIP");
        assertNotNull(result);
        System.out.println("场景15 - where+choose: " + result.size() + " 结果");
    }
    
    @Test
    public void testChooseWithMultipleIf() {
        List<User> result = userMapper.testChooseWithMultipleIf("VIP", "1");
        assertNotNull(result);
        System.out.println("场景16 - choose+多if: " + result.size() + " 结果");
    }
    
    // ========== 复杂场景测试 ==========
    
    @Test
    public void testFiveIf() {
        List<User> result = userMapper.testFiveIf("张", "zhang", "1", "VIP");
        assertNotNull(result);
        System.out.println("场景17 - 5个if: " + result.size() + " 结果");
    }
    
    @Test
    public void testChooseNestedChoose() {
        List<User> result = userMapper.testChooseNestedChoose("1", "VIP");
        assertNotNull(result);
        System.out.println("场景18 - choose嵌套: " + result.size() + " 结果");
    }
    
    @Test
    public void testComplexConditions() {
        List<User> result = userMapper.testComplexConditions("张", "zhang", "1", "VIP");
        assertNotNull(result);
        System.out.println("场景19 - 复杂条件: " + result.size() + " 结果");
    }
    
    @Test
    public void testDynamicOrderBy() {
        List<User> result = userMapper.testDynamicOrderBy("张", "id", "DESC");
        assertNotNull(result);
        System.out.println("场景20 - 动态排序: " + result.size() + " 结果");
    }
    
    // ========== 高级场景测试 ==========
    
    @Test
    public void testBindIf() {
        List<User> result = userMapper.testBindIf("张", "1");
        assertNotNull(result);
        System.out.println("场景21 - bind+if: " + result.size() + " 结果");
    }
    
    @Test
    public void testTrimPrefixSuffix() {
        List<User> result = userMapper.testTrimPrefixSuffix("张三", "zhangsan@test.com");
        assertNotNull(result);
        System.out.println("场景22 - trim前后缀: " + result.size() + " 结果");
    }
    
    @Test
    public void testForeachInsert() {
        User user1 = new User();
        user1.setName("Test1");
        user1.setEmail("test1@test.com");
        user1.setStatus("1");
        user1.setType("VIP");
        
        User user2 = new User();
        user2.setName("Test2");
        user2.setEmail("test2@test.com");
        user2.setStatus("1");
        user2.setType("NORMAL");
        
        List<User> users = Arrays.asList(user1, user2);
        int result = userMapper.testForeachInsert(users);
        assertTrue(result >= 0);
        System.out.println("场景23 - foreach批量插入: " + result + " 条");
    }
    
    @Test
    public void testDynamicColumns() {
        List<User> result = userMapper.testDynamicColumns(true, true, true, true, "张");
        assertNotNull(result);
        System.out.println("场景24 - 动态列名: " + result.size() + " 结果");
    }
    
    @Test
    public void testChooseTripleNested() {
        List<User> result = userMapper.testChooseTripleNested("1", "VIP", "张");
        assertNotNull(result);
        System.out.println("场景25 - 3层嵌套choose: " + result.size() + " 结果");
    }
    
    @Test
    public void testSetMultipleIf() {
        User user = new User();
        user.setId(1);
        user.setName("Updated");
        user.setEmail("updated@test.com");
        int result = userMapper.testSetMultipleIf(user);
        System.out.println("场景26 - set多字段更新: " + result + " 条");
    }
    
    @Test
    public void testIfMultiCondition() {
        List<User> result = userMapper.testIfMultiCondition("张三", "zhang@test.com", "1");
        assertNotNull(result);
        System.out.println("场景27 - if多条件: " + result.size() + " 结果");
    }
    
    @Test
    public void testForeachChoose() {
        List<User> result = userMapper.testForeachChoose(Arrays.asList(1, 2, 3), "1");
        assertNotNull(result);
        System.out.println("场景28 - foreach+choose: " + result.size() + " 结果");
    }
    
    @Test
    public void testTrimUpdate() {
        User user = new User();
        user.setId(1);
        user.setName("Updated2");
        user.setEmail("updated2@test.com");
        int result = userMapper.testTrimUpdate(user);
        System.out.println("场景29 - trim动态更新: " + result + " 条");
    }
    
    @Test
    public void testIfForeachComplex() {
        List<User> result = userMapper.testIfForeachComplex("1", Arrays.asList("VIP", "NORMAL"), "张", Arrays.asList(100, 200));
        assertNotNull(result);
        System.out.println("场景30 - 复杂if+foreach: " + result.size() + " 结果");
    }
    
    // ========== SQL 片段引用测试 (场景31-36) ==========
    
    @Test
    public void testIncludeBaseColumns() {
        User result = userMapper.testIncludeBaseColumns(1);
        System.out.println("场景31 - include基础列: " + (result != null ? result.getName() : "无结果"));
    }
    
    @Test
    public void testIncludeCondition() {
        List<User> result = userMapper.testIncludeCondition("1", "VIP");
        assertNotNull(result);
        System.out.println("场景32 - include条件片段: " + result.size() + " 结果");
    }
    
    @Test
    public void testMultipleInclude() {
        List<User> result = userMapper.testMultipleInclude("张", "zhang", "1");
        assertNotNull(result);
        System.out.println("场景33 - 多include组合: " + result.size() + " 结果");
    }
    
    @Test
    public void testIncludeComplex() {
        List<User> result = userMapper.testIncludeComplex("1", "VIP", "张");
        assertNotNull(result);
        System.out.println("场景34 - include复杂嵌套: " + result.size() + " 结果");
    }
    
    @Test
    public void testIncludeInIf() {
        List<User> result = userMapper.testIncludeInIf(true, false, "1", null);
        assertNotNull(result);
        System.out.println("场景35 - include嵌套if: " + result.size() + " 结果");
    }
    
    @Test
    public void testIncludeInChoose() {
        List<User> result = userMapper.testIncludeInChoose("status", "1", "VIP", "张", "zhang");
        assertNotNull(result);
        System.out.println("场景36 - include嵌套choose: " + result.size() + " 结果");
    }
    
    // ========== 高级 bind 测试 (场景37-38) ==========
    
    @Test
    public void testMultipleBind() {
        List<User> result = userMapper.testMultipleBind("张", "zhang", null);
        assertNotNull(result);
        System.out.println("场景37 - 多bind链式: " + result.size() + " 结果");
    }
    
    @Test
    public void testBindWithInclude() {
        List<User> result = userMapper.testBindWithInclude("1");
        assertNotNull(result);
        System.out.println("场景38 - bind+include组合: " + result.size() + " 结果");
    }
    
    // ========== 边界情况测试 (场景39-45) ==========
    
    @Test
    public void testEmptyIf() {
        List<User> result = userMapper.testEmptyIf();
        assertNotNull(result);
        System.out.println("场景39 - 空条件if: " + result.size() + " 结果");
    }
    
    @Test
    public void testOnlyOtherwise() {
        List<User> result = userMapper.testOnlyOtherwise();
        assertNotNull(result);
        System.out.println("场景40 - 只有otherwise: " + result.size() + " 结果");
    }
    
    @Test
    public void testNestedTrim() {
        List<User> result = userMapper.testNestedTrim("张", "zhang");
        assertNotNull(result);
        System.out.println("场景41 - 多层trim嵌套: " + result.size() + " 结果");
    }
    
    @Test
    public void testNestedForeach() {
        List<User> result = userMapper.testNestedForeach(Arrays.asList("active", "inactive", "other"));
        assertNotNull(result);
        System.out.println("场景42 - foreach嵌套choose: " + result.size() + " 结果");
    }
    
    @Test
    public void testIncludeWithProperty() {
        List<User> result = userMapper.testIncludeWithProperty("1");
        assertNotNull(result);
        System.out.println("场景43 - include传递参数: " + result.size() + " 结果");
    }
    
    @Test
    public void testLongConditions() {
        List<User> result = userMapper.testLongConditions("v1", "v2", null, "v4", null, null, "v7", null);
        assertNotNull(result);
        System.out.println("场景44 - 8条件压力测试: " + result.size() + " 结果");
    }
    
    @Test
    public void testInsertWithSelectKey() {
        User u1 = new User();
        u1.setName("NewUser1");
        u1.setEmail("new1@test.com");
        u1.setStatus("1");
        u1.setType("VIP");
        
        User u2 = new User();
        u2.setName("NewUser2");
        u2.setEmail("new2@test.com");
        // status 和 type 为 null，测试 otherwise
        
        int result = userMapper.testInsertWithSelectKey(Arrays.asList(u1, u2));
        System.out.println("场景45 - insert+choose组合: 插入 " + result + " 条");
    }
    
    // ========== 多表关联测试 (场景46-55) ==========
    
    @Test
    public void testInnerJoin() {
        List<UserOrderDTO> result = userMapper.testInnerJoin();
        assertNotNull(result);
        System.out.println("场景46 - 内连接: " + result.size() + " 结果");
    }
    
    @Test
    public void testLeftJoin() {
        List<UserOrderDTO> result = userMapper.testLeftJoin();
        assertNotNull(result);
        System.out.println("场景47 - 左外连接: " + result.size() + " 结果");
    }
    
    @Test
    public void testMultiTableJoin() {
        List<UserOrderItemDTO> result = userMapper.testMultiTableJoin(1);
        assertNotNull(result);
        System.out.println("场景48 - 多表连接: " + result.size() + " 结果");
    }
    
    @Test
    public void testDynamicJoin() {
        List<UserOrderDTO> result = userMapper.testDynamicJoin(1, "completed");
        assertNotNull(result);
        System.out.println("场景49 - 动态join: " + result.size() + " 结果");
    }
    
    @Test
    public void testSubqueryIn() {
        List<User> result = userMapper.testSubqueryIn(Arrays.asList(1, 2, 3));
        assertNotNull(result);
        System.out.println("场景50 - 子查询IN: " + result.size() + " 结果");
    }
    
    @Test
    public void testSubqueryExists() {
        List<User> result = userMapper.testSubqueryExists("completed");
        assertNotNull(result);
        System.out.println("场景51 - 子查询EXISTS: " + result.size() + " 结果");
    }
    
    @Test
    public void testScalarSubquery() {
        List<UserOrderCountDTO> result = userMapper.testScalarSubquery();
        assertNotNull(result);
        System.out.println("场景52 - 标量子查询: " + result.size() + " 结果");
    }
    
    @Test
    public void testDynamicMultiTableJoin() {
        List<UserOrderDTO> result = userMapper.testDynamicMultiTableJoin(1, "completed");
        assertNotNull(result);
        System.out.println("场景53 - 动态多表关联: " + result.size() + " 结果");
    }
    
    @Test
    public void testUnion() {
        List<User> result = userMapper.testUnion("VIP");
        assertNotNull(result);
        System.out.println("场景54 - UNION查询: " + result.size() + " 结果");
    }
    
    @Test
    public void testNestedSubquery() {
        List<UserOrderDTO> result = userMapper.testNestedSubquery(1000.0);
        assertNotNull(result);
        System.out.println("场景55 - 多层嵌套子查询: " + result.size() + " 结果");
    }
    
    // ========== 函数/聚合测试 (场景56-70) ==========
    
    @Test
    public void testCountAll() {
        int result = userMapper.testCountAll();
        assertTrue(result > 0);
        System.out.println("场景56 - COUNT聚合: " + result + " 条");
    }
    
    @Test
    public void testCountByStatus() {
        int result = userMapper.testCountByStatus("1");
        System.out.println("场景57 - COUNT条件聚合: " + result + " 条");
    }
    
    @Test
    public void testSumAmount() {
        Double result = userMapper.testSumAmount();
        assertNotNull(result);
        System.out.println("场景58 - SUM聚合: " + result);
    }
    
    @Test
    public void testAvgAmount() {
        Double result = userMapper.testAvgAmount();
        assertNotNull(result);
        System.out.println("场景59 - AVG聚合: " + result);
    }
    
    @Test
    public void testMaxMinAmount() {
        OrderAmountDTO result = userMapper.testMaxMinAmount();
        assertNotNull(result);
        System.out.println("场景60 - MAX/MIN聚合: max=" + result.getMaxAmount() + ", min=" + result.getMinAmount());
    }
    
    @Test
    public void testGroupBy() {
        List<OrderStatusCountDTO> result = userMapper.testGroupBy();
        assertNotNull(result);
        System.out.println("场景61 - GROUP BY: " + result.size() + " 组");
    }
    
    @Test
    public void testMultiGroupBy() {
        List<OrderUserStatusDTO> result = userMapper.testMultiGroupBy(1);
        assertNotNull(result);
        System.out.println("场景62 - 多字段分组: " + result.size() + " 组");
    }
    
    @Test
    public void testGroupByHaving() {
        List<OrderStatusCountDTO> result = userMapper.testGroupByHaving(1);
        assertNotNull(result);
        System.out.println("场景63 - HAVING过滤: " + result.size() + " 组");
    }
    
    @Test
    public void testCaseWhen() {
        List<OrderCaseDTO> result = userMapper.testCaseWhen();
        assertNotNull(result);
        System.out.println("场景64 - CASE WHEN: " + result.size() + " 条");
    }
    
    @Test
    public void testDateFunction() {
        List<OrderDateDTO> result = userMapper.testDateFunction(2024);
        assertNotNull(result);
        System.out.println("场景65 - DATE函数: " + result.size() + " 条");
    }
    
    @Test
    public void testStringConcat() {
        List<User> result = userMapper.testStringConcat("张");
        assertNotNull(result);
        System.out.println("场景66 - 字符串CONCAT: " + result.size() + " 条");
    }
    
    @Test
    public void testStringSubstring() {
        List<User> result = userMapper.testStringSubstring("zha");
        assertNotNull(result);
        System.out.println("场景67 - 字符串SUBSTRING: " + result.size() + " 条");
    }
    
    @Test
    public void testConditionalSum() {
        Double result = userMapper.testConditionalSum("completed");
        assertNotNull(result);
        System.out.println("场景68 - 条件聚合SUM: " + result);
    }
    
    @Test
    public void testMultiAggFunction() {
        List<OrderAggDTO> result = userMapper.testMultiAggFunction();
        assertNotNull(result);
        System.out.println("场景69 - 多函数组合: " + result.size() + " 组");
    }
    
    @Test
    public void testOrderRank() {
        List<OrderRankDTO> result = userMapper.testOrderRank();
        assertNotNull(result);
        System.out.println("场景70 - 订单排名: " + result.size() + " 条");
    }
    
    // ========== 分页测试 (场景71-75) ==========
    
    @Test
    public void testLimit() {
        List<Order> result = userMapper.testLimit(5);
        assertNotNull(result);
        assertTrue(result.size() <= 5);
        System.out.println("场景71 - LIMIT分页: " + result.size() + " 条");
    }
    
    @Test
    public void testLimitOffset() {
        List<Order> result = userMapper.testLimitOffset(3, 2);
        assertNotNull(result);
        System.out.println("场景72 - LIMIT+OFFSET: " + result.size() + " 条");
    }
    
    @Test
    public void testDynamicPagination() {
        List<Order> result = userMapper.testDynamicPagination(3, 3);
        assertNotNull(result);
        System.out.println("场景73 - 动态分页: " + result.size() + " 条");
    }
    
    // ========== DISTINCT 测试 (场景76-78) ==========
    
    @Test
    public void testDistinctStatus() {
        List<String> result = userMapper.testDistinctStatus();
        assertNotNull(result);
        System.out.println("场景76 - DISTINCT去重: " + result.size() + " 种状态");
    }
    
    @Test
    public void testDistinctMultipleFields() {
        List<User> result = userMapper.testDistinctMultipleFields();
        assertNotNull(result);
        System.out.println("场景77 - DISTINCT多字段: " + result.size() + " 条");
    }
    
    // ========== 数据库特有语法 (场景79-85) ==========
    
    @Test
    public void testInsertOnDuplicateKeyUpdate() {
        User user = new User();
        user.setId(1);
        user.setName("TestUser");
        user.setEmail("test@example.com");
        user.setStatus("1");
        user.setType("VIP");
        int result = userMapper.testInsertOnDuplicateKeyUpdate(user);
        System.out.println("场景79 - ON DUPLICATE KEY: " + result);
    }
    
    @Test
    public void testReturningSyntax() {
        List<Order> result = userMapper.testReturningSyntax();
        assertNotNull(result);
        System.out.println("场景80 - RETURNING语法: " + result.size() + " 条");
    }
    
    @Test
    public void testDistinctWithCondition() {
        List<String> result = userMapper.testDistinctWithCondition("completed");
        assertNotNull(result);
        System.out.println("场景81 - DISTINCT+条件: " + result.size() + " 条");
    }
    
    @Test
    public void testCountDistinct() {
        int result = userMapper.testCountDistinct("completed");
        assertTrue(result >= 0);
        System.out.println("场景82 - COUNT DISTINCT: " + result + " 个用户");
    }
    
    @Test
    public void testOrderByMultipleWithPagination() {
        List<Order> result = userMapper.testOrderByMultipleWithPagination(5, 0);
        assertNotNull(result);
        System.out.println("场景83 - 多字段排序+分页: " + result.size() + " 条");
    }
    
    @Test
    public void testComplexAggregation() {
        List<OrderStatusCountDTO> result = userMapper.testComplexAggregation(100.0);
        assertNotNull(result);
        System.out.println("场景84 - 复杂聚合: " + result.size() + " 组");
    }
    
    @Test
    public void testUnionWithLimit() {
        List<User> result = userMapper.testUnionWithLimit("VIP", 5);
        assertNotNull(result);
        System.out.println("场景85 - UNION+LIMIT: " + result.size() + " 条");
    }
    
    // ========== 场景86-95: 跨文件 SQL 片段引用测试 ==========
    
    @Test
    public void testCrossFileInclude() {
        List<User> result = userMapper.testCrossFileInclude("1");
        assertNotNull(result);
        System.out.println("场景86 - 跨文件引用: " + result.size() + " 条");
    }
    
    @Test
    public void testCrossFileIncludeWithIf() {
        List<User> result = userMapper.testCrossFileIncludeWithIf("张三", "1");
        assertNotNull(result);
        System.out.println("场景87 - 跨文件+本地if: " + result.size() + " 条");
    }
    
    @Test
    public void testLocalFragmentWithCrossFile() {
        List<User> result = userMapper.testLocalFragmentWithCrossFile("VIP", "1", null, null);
        assertNotNull(result);
        System.out.println("场景88 - 本地片段跨文件: " + result.size() + " 条");
    }
    
    @Test
    public void testCrossFileInChoose() {
        List<User> result = userMapper.testCrossFileInChoose("active", "1", null, null);
        assertNotNull(result);
        System.out.println("场景89 - choose内跨文件: " + result.size() + " 条");
    }
    
    @Test
    public void testCrossFileWithForeach() {
        List<Integer> ids = Arrays.asList(1, 2, 3);
        List<User> result = userMapper.testCrossFileWithForeach(ids, "1", 10, 0);
        assertNotNull(result);
        System.out.println("场景90 - foreach+跨文件: " + result.size() + " 条");
    }
    
    @Test
    public void testMultipleCrossFileInclude() {
        List<User> result = userMapper.testMultipleCrossFileInclude("1");
        assertNotNull(result);
        System.out.println("场景91 - 多次跨文件引用: " + result.size() + " 条");
    }
    
    @Test
    public void testCrossFileNestedChoose() {
        List<User> result = userMapper.testCrossFileNestedChoose(true, "1", "VIP");
        assertNotNull(result);
        System.out.println("场景92 - 跨文件嵌套choose: " + result.size() + " 条");
    }
    
    @Test
    public void testCrossFileInTrim() {
        List<User> result = userMapper.testCrossFileInTrim("1", "VIP");
        assertNotNull(result);
        System.out.println("场景93 - trim内跨文件: " + result.size() + " 条");
    }
    
    @Test
    public void testCrossFileInSet() {
        int result = userMapper.testCrossFileInSet("1", "VIP");
        assertTrue(result >= 0);
        System.out.println("场景94 - set内跨文件: " + result + " 条");
    }
    
    @Test
    public void testChainedCrossFileInclude() {
        List<User> result = userMapper.testChainedCrossFileInclude("1", "VIP");
        assertNotNull(result);
        System.out.println("场景95 - 三层引用链: " + result.size() + " 条");
    }
    
    // ========== selectKey 测试 (S1-S4) ==========
    
    @Test
    public void testSelectKeyOracle() {
        User user = new User();
        user.setName("TestOracle");
        user.setEmail("oracle@test.com");
        int result = userMapper.testSelectKeyOracle(user);
        assertTrue(result > 0);
        System.out.println("S1 - selectKey Oracle: " + result + " 条");
    }
    
    @Test
    public void testSelectKeyPostgres() {
        User user = new User();
        user.setName("TestPostgres");
        user.setEmail("postgres@test.com");
        int result = userMapper.testSelectKeyPostgres(user);
        assertTrue(result > 0);
        System.out.println("S2 - selectKey Postgres: " + result + " 条");
    }
    
    @Test
    public void testSelectKeyMysql() {
        User user = new User();
        user.setName("TestMysql");
        user.setEmail("mysql@test.com");
        int result = userMapper.testSelectKeyMysql(user);
        assertTrue(result > 0);
        System.out.println("S3 - selectKey MySQL: " + result + " 条");
    }
    
    @Test
    public void testSelectKeyUuid() {
        User user = new User();
        user.setName("TestUuid");
        user.setEmail("uuid@test.com");
        int result = userMapper.testSelectKeyUuid(user);
        assertTrue(result > 0);
        System.out.println("S4 - selectKey UUID: " + result + " 条");
    }
    
    // ========== resultMap 嵌套测试 (R1-R6) ==========
    
    @Test
    public void testResultMapAssociation() {
        List<UserOrderNestedDTO> result = userMapper.testResultMapAssociation();
        assertNotNull(result);
        System.out.println("R1 - resultMap association: " + result.size() + " 条");
    }
    
    @Test
    public void testResultMapCollection() {
        List<UserWithOrdersDTO> result = userMapper.testResultMapCollection();
        assertNotNull(result);
        System.out.println("R2 - resultMap collection: " + result.size() + " 条");
    }
    
    @Test
    public void testResultMapNoId() {
        List<User> result = userMapper.testResultMapNoId();
        assertNotNull(result);
        System.out.println("R3 - resultMap no id: " + result.size() + " 条");
    }
    
    @Test
    public void testNestedSelectN1() {
        List<UserWithOrdersDTO> result = userMapper.testNestedSelectN1();
        assertNotNull(result);
        System.out.println("R4 - nested select N+1: " + result.size() + " 条");
    }
    
    @Test
    public void testNestedResult() {
        List<UserWithOrdersDTO> result = userMapper.testNestedResult();
        assertNotNull(result);
        System.out.println("R5 - nested result: " + result.size() + " 条");
    }
    
    @Test
    public void testDiscriminator() {
        List<User> result = userMapper.testDiscriminator();
        assertNotNull(result);
        System.out.println("R6 - discriminator: " + result.size() + " 条");
    }
    
    // ========== 子查询诊断测试 (Q1-Q3) ==========
    
    @Test
    public void testCorrelatedSubquery() {
        List<User> result = userMapper.testCorrelatedSubquery();
        assertNotNull(result);
        System.out.println("Q1 - correlated subquery: " + result.size() + " 条");
    }
    
    @Test
    public void testScalarSubqueryNew() {
        List<UserOrderCountDTO> result = userMapper.testScalarSubqueryNew();
        assertNotNull(result);
        System.out.println("Q2 - scalar subquery: " + result.size() + " 条");
    }
    
    @Test
    public void testNestedSubqueryComplex() {
        List<User> result = userMapper.testNestedSubqueryComplex();
        assertNotNull(result);
        System.out.println("Q3 - nested subquery: " + result.size() + " 条");
    }
}
