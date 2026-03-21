package com.test.entity;

import lombok.Data;
import java.math.BigDecimal;

@Data
public class Product {
    private Long id;
    private String name;
    private String category;
    private BigDecimal price;
    private Integer stock;
    private Integer status;
}
