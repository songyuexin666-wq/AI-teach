package com.example.demo.controller;

import com.example.demo.entity.PaperManage;
import com.example.demo.service.PaperManageService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/paper-manage")
@CrossOrigin
public class PaperManageController {
    @Autowired
    private PaperManageService service;
    @GetMapping("/list")
    public List<PaperManage> list() { return service.findAll(); }
    @PostMapping("/add")
    public PaperManage add(@RequestBody PaperManage t) { return service.save(t); }
    @PutMapping("/update")
    public PaperManage update(@RequestBody PaperManage t) { return service.save(t); }
    @DeleteMapping("/delete/{id}")
    public void delete(@PathVariable Long id) { service.deleteById(id); }
    @GetMapping("/{id}")
    public Optional<PaperManage> getById(@PathVariable Long id) { return service.findById(id); }
} 