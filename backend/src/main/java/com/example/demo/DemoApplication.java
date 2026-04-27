package com.example.demo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.http.ResponseEntity;
import java.util.HashMap;
import java.util.Map;

@SpringBootApplication
@RestController
@RequestMapping("/api")
public class DemoApplication {
    
    public static void main(String[] args) {
        SpringApplication.run(DemoApplication.class, args);
    }
    
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        Map<String, Object> response = new HashMap<>();
        response.put("status", "UP");
        response.put("service", "AI教师助手Spring Boot后端");
        response.put("port", "8080");
        response.put("timestamp", System.currentTimeMillis());
        return ResponseEntity.ok(response);
    }
    
    @GetMapping("/info")
    public ResponseEntity<Map<String, Object>> info() {
        Map<String, Object> response = new HashMap<>();
        response.put("name", "AI教师助手系统");
        response.put("version", "1.0.0");
        response.put("description", "智能AI教学系统后端服务");
        response.put("endpoints", new String[]{
            "/api/health",
            "/api/info", 
            "/api/paper-manage/list",
            "/api/teach-design/list"
        });
        return ResponseEntity.ok(response);
    }
}
