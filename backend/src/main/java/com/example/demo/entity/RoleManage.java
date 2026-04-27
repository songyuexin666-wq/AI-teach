package com.example.demo.entity;

import lombok.Data;
import javax.persistence.*;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "role_manage")
public class RoleManage {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    private String permission;
    private String status;
    @Column(name = "create_time")
    private LocalDateTime createTime;
} 