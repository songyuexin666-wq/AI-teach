package com.example.demo.controller;

import com.example.demo.entity.TeachDesign;
import com.example.demo.service.TeachDesignService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/teach-design")
@CrossOrigin
public class TeachDesignController {
    @Autowired
    private TeachDesignService service;
    @GetMapping("/list")
    public List<TeachDesign> list() { return service.findAll(); }
    @PostMapping("/add")
    public TeachDesign add(@RequestBody TeachDesign t) { return service.save(t); }
    @PutMapping("/update")
    public TeachDesign update(@RequestBody TeachDesign t) { return service.save(t); }
    @DeleteMapping("/delete/{id}")
    public void delete(@PathVariable Long id) { service.deleteById(id); }
    @GetMapping("/{id}")
    public Optional<TeachDesign> getById(@PathVariable Long id) { return service.findById(id); }
} 