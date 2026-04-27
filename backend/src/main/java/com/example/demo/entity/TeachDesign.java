package com.example.demo.entity;

import lombok.Data;
import javax.persistence.*;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "teach_design")
public class TeachDesign {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String course;
    private String teacher;
    private String status;
    @Column(name = "create_time")
    private LocalDateTime createTime;
} 