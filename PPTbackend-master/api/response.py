"""
统一的API响应格式
"""
from typing import Any, Dict, Optional, Union
from fastapi.responses import JSONResponse
from fastapi import status


class APIResponse:
    """统一的API响应类"""
    
    @staticmethod
    def success(
        data: Any = None,
        message: str = "操作成功",
        code: int = 200,
        **kwargs
    ) -> JSONResponse:
        """
        成功响应
        
        Args:
            data: 响应数据
            message: 响应消息
            code: 状态码
            **kwargs: 其他字段
            
        Returns:
            JSONResponse: 统一格式的成功响应
        """
        response_data = {
            "success": True,
            "code": code,
            "message": message,
            "data": data,
            "timestamp": kwargs.get("timestamp"),
            "request_id": kwargs.get("request_id")
        }
        
        # 添加其他字段
        for key, value in kwargs.items():
            if key not in ["timestamp", "request_id"]:
                response_data[key] = value
        
        return JSONResponse(
            status_code=code,
            content=response_data
        )
    
    @staticmethod
    def error(
        message: str = "操作失败",
        code: int = 400,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> JSONResponse:
        """
        错误响应
        
        Args:
            message: 错误消息
            code: HTTP状态码
            error_code: 业务错误码
            details: 错误详情
            **kwargs: 其他字段
            
        Returns:
            JSONResponse: 统一格式的错误响应
        """
        response_data = {
            "success": False,
            "code": code,
            "message": message,
            "error_code": error_code,
            "details": details,
            "timestamp": kwargs.get("timestamp"),
            "request_id": kwargs.get("request_id")
        }
        
        # 添加其他字段
        for key, value in kwargs.items():
            if key not in ["timestamp", "request_id"]:
                response_data[key] = value
        
        return JSONResponse(
            status_code=code,
            content=response_data
        )
    
    @staticmethod
    def validation_error(
        message: str = "数据验证失败",
        errors: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> JSONResponse:
        """
        数据验证错误响应
        
        Args:
            message: 错误消息
            errors: 验证错误详情
            **kwargs: 其他字段
            
        Returns:
            JSONResponse: 验证错误响应
        """
        return APIResponse.error(
            message=message,
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            details={"validation_errors": errors},
            **kwargs
        )
    
    @staticmethod
    def not_found(
        message: str = "资源不存在",
        resource: Optional[str] = None,
        **kwargs
    ) -> JSONResponse:
        """
        资源不存在响应
        
        Args:
            message: 错误消息
            resource: 资源类型
            **kwargs: 其他字段
            
        Returns:
            JSONResponse: 404响应
        """
        return APIResponse.error(
            message=message,
            code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details={"resource": resource} if resource else None,
            **kwargs
        )
    
    @staticmethod
    def unauthorized(
        message: str = "未授权访问",
        **kwargs
    ) -> JSONResponse:
        """
        未授权响应
        
        Args:
            message: 错误消息
            **kwargs: 其他字段
            
        Returns:
            JSONResponse: 401响应
        """
        return APIResponse.error(
            message=message,
            code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            **kwargs
        )
    
    @staticmethod
    def forbidden(
        message: str = "权限不足",
        **kwargs
    ) -> JSONResponse:
        """
        权限不足响应
        
        Args:
            message: 错误消息
            **kwargs: 其他字段
            
        Returns:
            JSONResponse: 403响应
        """
        return APIResponse.error(
            message=message,
            code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
            **kwargs
        )
    
    @staticmethod
    def internal_error(
        message: str = "服务器内部错误",
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> JSONResponse:
        """
        服务器内部错误响应
        
        Args:
            message: 错误消息
            details: 错误详情
            **kwargs: 其他字段
            
        Returns:
            JSONResponse: 500响应
        """
        return APIResponse.error(
            message=message,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_ERROR",
            details=details,
            **kwargs
        )
    
    @staticmethod
    def rate_limit_exceeded(
        message: str = "请求过于频繁",
        retry_after: Optional[int] = None,
        **kwargs
    ) -> JSONResponse:
        """
        请求频率限制响应
        
        Args:
            message: 错误消息
            retry_after: 重试等待时间（秒）
            **kwargs: 其他字段
            
        Returns:
            JSONResponse: 429响应
        """
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        
        response_data = {
            "success": False,
            "code": status.HTTP_429_TOO_MANY_REQUESTS,
            "message": message,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "retry_after": retry_after,
            "timestamp": kwargs.get("timestamp"),
            "request_id": kwargs.get("request_id")
        }
        
        # 添加其他字段
        for key, value in kwargs.items():
            if key not in ["timestamp", "request_id"]:
                response_data[key] = value
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=response_data,
            headers=headers
        )


# 便捷函数
def success_response(data: Any = None, message: str = "操作成功", **kwargs) -> JSONResponse:
    """成功响应便捷函数"""
    return APIResponse.success(data=data, message=message, **kwargs)


def error_response(message: str = "操作失败", code: int = 400, **kwargs) -> JSONResponse:
    """错误响应便捷函数"""
    return APIResponse.error(message=message, code=code, **kwargs)


def validation_error_response(message: str = "数据验证失败", errors: Dict[str, Any] = None, **kwargs) -> JSONResponse:
    """验证错误响应便捷函数"""
    return APIResponse.validation_error(message=message, errors=errors, **kwargs)


def not_found_response(message: str = "资源不存在", resource: str = None, **kwargs) -> JSONResponse:
    """资源不存在响应便捷函数"""
    return APIResponse.not_found(message=message, resource=resource, **kwargs)


def internal_error_response(message: str = "服务器内部错误", details: Dict[str, Any] = None, **kwargs) -> JSONResponse:
    """内部错误响应便捷函数"""
    return APIResponse.internal_error(message=message, details=details, **kwargs)









