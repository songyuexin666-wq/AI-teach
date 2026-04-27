-- 更新数据库表结构以支持中文字符
USE ai_teach;

-- 添加full_name字段（如果不存在）
ALTER TABLE users ADD COLUMN full_name VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 添加college字段（如果不存在）
ALTER TABLE users ADD COLUMN college VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 添加major字段（如果不存在）
ALTER TABLE users ADD COLUMN major VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 更新现有字段的字符集
ALTER TABLE users MODIFY username VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE users MODIFY password VARCHAR(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE users MODIFY role VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 显示表结构
DESCRIBE users; 