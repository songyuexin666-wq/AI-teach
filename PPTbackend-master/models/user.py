from sqlalchemy import Column, Integer, String, Text
from models.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(128), nullable=False)
    role = Column(String(20), default="student")
    name = Column(String(100), nullable=True)  # 姓名
    college = Column(String(100), nullable=True)  # 学院
    major = Column(String(100), nullable=True)    # 专业
    courses = Column(Text, nullable=True)        # 教师任教课程，JSON 数组字符串，如 ["高等数学","线性代数"]