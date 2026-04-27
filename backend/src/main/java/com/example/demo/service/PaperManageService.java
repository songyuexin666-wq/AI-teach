package com.example.demo.service;

import com.example.demo.entity.PaperManage;
import java.util.List;
import java.util.Optional;

public interface PaperManageService {
    List<PaperManage> findAll();
    PaperManage save(PaperManage t);
    void deleteById(Long id);
    Optional<PaperManage> findById(Long id);
} 