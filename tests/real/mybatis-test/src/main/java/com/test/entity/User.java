package com.test.entity;

import lombok.Data;
import lombok.experimental.Accessors;
import java.time.LocalDateTime;

@Data
@Accessors(chain = true)
public class User {
    private Integer id;
    private String name;
    private String email;
    private String status;
    private String type;
    private LocalDateTime createdAt;
}
