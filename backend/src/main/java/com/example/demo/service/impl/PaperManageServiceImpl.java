package com.example.demo.service.impl;

import com.example.demo.entity.PaperManage;
import com.example.demo.repository.PaperManageRepository;
import com.example.demo.service.PaperManageService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class PaperManageServiceImpl implements PaperManageService {
    @Autowired
    private PaperManageRepository repo;
    public List<PaperManage> findAll() { return repo.findAll(); }
    public PaperManage save(PaperManage t) { return repo.save(t); }
    public void deleteById(Long id) { repo.deleteById(id); }
    public Optional<PaperManage> findById(Long id) { return repo.findById(id); }
} 