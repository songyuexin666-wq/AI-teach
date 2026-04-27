package com.example.demo.entity;

import lombok.Data;
import javax.persistence.*;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "menu_manage")
public class MenuManage {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    private String icon;
    @Column(name = "`order`")
    private Integer order;
    private String status;
    @Column(name = "create_time")
    private LocalDateTime createTime;
} 