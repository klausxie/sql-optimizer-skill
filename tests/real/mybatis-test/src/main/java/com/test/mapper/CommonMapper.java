package com.test.mapper;

import org.apache.ibatis.annotations.Mapper;

/**
 * 通用 Mapper - 定义可复用的 SQL 片段
 * 注意：这个 Mapper 主要用于定义 <sql> 片段，不需要实际的查询方法
 */
@Mapper
public interface CommonMapper {
    // 此 Mapper 主要用于定义跨文件复用的 SQL 片段
    // 不需要具体的查询方法
}
