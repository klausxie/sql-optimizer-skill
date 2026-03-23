# MyBatis 动态 SQL 分支测试项目

这是一个用于测试 MyBatis 动态 SQL 分支推断功能的 Spring Boot 项目。

## 技术栈

- Spring Boot 3.2.0
- JDK 21
- MyBatis 3.0.3
- H2 Database (内存数据库)

## 项目结构

```
mybatis-test/
├── src/main/
│   ├── java/com/test/
│   │   ├── MybatisTestApplication.java    # Spring Boot 启动类
│   │   ├── entity/                        # 实体类
│   │   │   ├── User.java
│   │   │   ├── Order.java
│   │   │   └── Product.java
│   │   ├── mapper/                         # Mapper 接口
│   │   │   └── UserMapper.java
│   │   └── controller/
│   │       └── TestController.java        # REST API
│   └── resources/
│       ├── application.yml                 # 配置文件
│       ├── schema.sql                     # 表结构
│       ├── data.sql                       # 测试数据
│       └── mapper/
│           ├── basic/                      # 基础场景 (10个)
│           │   └── BasicScenarios.xml
│           ├── combination/                # 组合场景 (6个)
│           │   └── CombinationScenarios.xml
│           └── complex/                   # 复杂场景 (5个)
│               └── ComplexScenarios.xml
└── src/test/
    └── java/com/test/
        └── MyBatisBranchTest.java         # 单元测试
```

## 测试场景

### 基础场景 (10个)

| 场景 | XML标签组合 | 预期分支数 |
|------|------------|------------|
| 1 | 单个 `<if>` | 2 |
| 2 | 2个 `<if>` 组合 | 4 (2²) |
| 3 | 3个 `<if>` 组合 | 8 (2³) |
| 4 | 4个 `<if>` 组合 | 16 (2⁴) |
| 5 | `<choose>` + 2个 `<when>` | 2 |
| 6 | `<choose>` + `<when>` + `<otherwise>` | 3 |
| 7 | `<where>` + `<if>` | 2 |
| 8 | `<set>` + `<if>` | 2 |
| 9 | `<foreach>` | 1 (示例) |
| 10 | `<trim>` | 2 |

### 组合场景 (6个)

| 场景 | XML标签组合 | 预期分支数 |
|------|------------|------------|
| 11 | `<if>` + `<choose>` 嵌套 | 4-6 |
| 12 | `<where>` + 多个 `<if>` | 16 (2⁴) |
| 13 | `<choose>` + 多个 `<if>` | 5-7 |
| 14 | `<if>` + `<foreach>` 嵌套 | 4 |
| 15 | `<where>` + `<choose>` + `<when>` | 4-6 |
| 16 | `<choose>` 内嵌多个 `<if>` | 5-7 |

### 复杂场景 (5个)

| 场景 | XML标签组合 | 预期分支数 |
|------|------------|------------|
| 17 | 5个 `<if>` 条件 | 32 (2⁵) |
| 18 | `<choose>` 嵌套 `<choose>` | 7-9 |
| 19 | 复杂多条件组合 | 8-12 |
| 20 | 动态排序 (`${}`) | 2-4 |

## 运行方式

### 方式1: 运行测试

```bash
cd /Users/hzz/workspace/mybatis-test
mvn test
```

### 方式2: 启动应用

```bash
mvn spring-boot:run
```

### 方式3: API 测试

启动后访问: http://localhost:8080

```bash
# 基础场景测试
curl "http://localhost:8080/api/test/basic/single-if?username=张三"
curl "http://localhost:8080/api/test/basic/two-if?username=张三&email=zhangsan@example.com"
curl "http://localhost:8080/api/test/basic/three-if?username=张三&email=zhangsan@example.com&status=1"

# 组合场景测试
curl "http://localhost:8080/api/test/combination/if-choose?status=1&userType=VIP"

# 复杂场景测试
curl "http://localhost:8080/api/test/complex/five-if?username=张&email=zhang&status=1&userType=VIP&city=北京"

# foreach 测试
curl "http://localhost:8080/api/test/basic/foreach?ids=1,2,3"
```

### 方式4: H2 Console

访问: http://localhost:8080/h2-console

- JDBC URL: `jdbc:h2:mem:testdb`
- Username: `sa`
- Password: (空)

## 分支数计算说明

### If 条件分支计算

每个 `<if>` 条件产生 2 个分支（成立/不成立）：
- 1个if: 2 = 2¹
- 2个if: 4 = 2²
- 3个if: 8 = 2³
- 4个if: 16 = 2⁴
- n个if: 2ⁿ

### Choose 条件分支计算

`<choose>` 产生 N+M 个分支：
- N = `<when>` 数量
- M = 1 (如果有 `<otherwise>`)

### 嵌套组合

嵌套时会将各部分分支数相乘：
- If(2) × Choose(3) = 6 分支

## 验证方法

使用 sql-optimizer 工具验证分支：

```bash
cd /Users/hzz/workspace/sqlopt

# 分析基础场景
node bin/sql-optimizer.js branches ../mybatis-test/src/main/resources/mapper/basic/BasicScenarios.xml

# 分析组合场景
node bin/sql-optimizer.js branches ../mybatis-test/src/main/resources/mapper/combination/CombinationScenarios.xml

# 分析复杂场景
node bin/sql-optimizer.js branches ../mybatis-test/src/main/resources/mapper/complex/ComplexScenarios.xml
```

## 扩展场景

如需添加更多测试场景，可以：

1. 在 `UserMapper.java` 添加新方法
2. 在对应的 XML 文件中添加 SQL 映射
3. 在 `TestController.java` 添加新的 API 端点
4. 在 `MyBatisBranchTest.java` 添加测试用例
