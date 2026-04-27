package com.example.demo.service;

import com.example.demo.entity.TeachDesign;
import java.util.List;
import java.util.Optional;

public interface TeachDesignService {
    List<TeachDesign> findAll();
    TeachDesign save(TeachDesign t);
    void deleteById(Long id);
    Optional<TeachDesign> findById(Long id);
} 