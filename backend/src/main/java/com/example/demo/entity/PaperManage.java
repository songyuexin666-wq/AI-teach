package com.example.demo.entity;

import lombok.Data;
import javax.persistence.*;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "paper_manage")
public class PaperManage {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String title;
    private String teacher;
    private String course;
    private Integer totalScore;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
} 