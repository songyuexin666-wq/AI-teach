package com.example.demo.service.impl;

import com.example.demo.entity.TeachDesign;
import com.example.demo.repository.TeachDesignRepository;
import com.example.demo.service.TeachDesignService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class TeachDesignServiceImpl implements TeachDesignService {
    @Autowired
    private TeachDesignRepository repo;
    public List<TeachDesign> findAll() { return repo.findAll(); }
    public TeachDesign save(TeachDesign t) { return repo.save(t); }
    public void deleteById(Long id) { repo.deleteById(id); }
    public Optional<TeachDesign> findById(Long id) { return repo.findById(id); }
} 