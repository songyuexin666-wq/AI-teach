from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量中获取数据库连接URL，如果没有则使用默认的ai_teach数据库
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/ai_teach")

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    echo=True  # 添加调试信息
)

# 创建一个数据库会话类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建一个所有数据模型的基类
Base = declarative_base()

# 创建一个依赖项，用于在API路由中获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 