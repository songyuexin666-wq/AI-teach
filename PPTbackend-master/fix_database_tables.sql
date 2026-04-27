-- 修复数据库表结构的SQL脚本
-- 为papers表添加缺失的字段

-- 添加description字段到papers表
ALTER TABLE papers ADD COLUMN description TEXT COMMENT '试卷描述';

-- 添加subject字段到papers表
ALTER TABLE papers ADD COLUMN subject VARCHAR(50) COMMENT '科目';

-- 添加grade字段到papers表
ALTER TABLE papers ADD COLUMN grade VARCHAR(20) COMMENT '年级';

-- 添加duration字段到papers表
ALTER TABLE papers ADD COLUMN duration INT COMMENT '考试时长（分钟）';

-- 添加total_score字段到papers表
ALTER TABLE papers ADD COLUMN total_score INT COMMENT '总分';

-- 添加difficulty字段到papers表
ALTER TABLE papers ADD COLUMN difficulty VARCHAR(20) COMMENT '难度：简单、中等、困难';

-- 添加content字段到papers表
ALTER TABLE papers ADD COLUMN content TEXT COMMENT '试卷内容';

-- 添加updated_at字段到papers表
ALTER TABLE papers ADD COLUMN updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- 为teach_designs表添加缺失的字段（如果需要）
ALTER TABLE teach_designs ADD COLUMN version INT DEFAULT 1 COMMENT '版本号';
ALTER TABLE teach_designs ADD COLUMN content TEXT COMMENT '设计内容';
ALTER TABLE teach_designs ADD COLUMN objectives TEXT COMMENT '教学目标';
ALTER TABLE teach_designs ADD COLUMN materials TEXT COMMENT '教学材料';
ALTER TABLE teach_designs ADD COLUMN activities TEXT COMMENT '教学活动';
ALTER TABLE teach_designs ADD COLUMN assessment TEXT COMMENT '评估方式';
ALTER TABLE teach_designs ADD COLUMN updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- 为major_info表添加缺失的字段（如果需要）
ALTER TABLE major_info ADD COLUMN description TEXT COMMENT '专业描述';
ALTER TABLE major_info ADD COLUMN updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- 为system_configs表添加缺失的字段（如果需要）
ALTER TABLE system_configs ADD COLUMN config_type VARCHAR(20) DEFAULT 'string' COMMENT '配置类型：string、int、float、boolean、json';
ALTER TABLE system_configs ADD COLUMN description VARCHAR(200) COMMENT '配置描述';
ALTER TABLE system_configs ADD COLUMN is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用';
ALTER TABLE system_configs ADD COLUMN updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- 为users表添加教师任教课程（JSON 数组字符串，可选）
ALTER TABLE users ADD COLUMN courses TEXT COMMENT '教师任教课程，JSON数组如["高等数学","线性代数"]';

-- 为system_logs表添加缺失的字段（如果需要）
ALTER TABLE system_logs ADD COLUMN user_id INT COMMENT '用户ID';
ALTER TABLE system_logs ADD COLUMN username VARCHAR(50) COMMENT '用户名';
ALTER TABLE system_logs ADD COLUMN action VARCHAR(100) COMMENT '操作类型';
ALTER TABLE system_logs ADD COLUMN module VARCHAR(50) COMMENT '模块名称';
ALTER TABLE system_logs ADD COLUMN description TEXT COMMENT '操作描述';
ALTER TABLE system_logs ADD COLUMN ip_address VARCHAR(50) COMMENT 'IP地址';
ALTER TABLE system_logs ADD COLUMN user_agent VARCHAR(500) COMMENT '用户代理';
ALTER TABLE system_logs ADD COLUMN status VARCHAR(20) DEFAULT 'success' COMMENT '操作状态：success、error、warning';
ALTER TABLE system_logs ADD COLUMN request_data TEXT COMMENT '请求数据';
ALTER TABLE system_logs ADD COLUMN response_data TEXT COMMENT '响应数据';
ALTER TABLE system_logs ADD COLUMN error_message TEXT COMMENT '错误信息';

-- 显示表结构确认修改
DESCRIBE papers;
DESCRIBE teach_designs;
DESCRIBE major_info;
DESCRIBE system_configs;
DESCRIBE system_logs; 