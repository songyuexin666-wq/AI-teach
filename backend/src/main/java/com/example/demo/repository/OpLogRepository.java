package com.example.demo.repository;

import com.example.demo.entity.OpLog;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OpLogRepository extends JpaRepository<OpLog, Long> {} 