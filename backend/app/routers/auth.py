"""
认证路由 - 处理用户登录、注册、登出
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.models.user import (
    UserLoginRequest, UserRegisterRequest, 
    UserResponse, LoginResponse
)
from app.services.user_service import get_user_service

router = APIRouter()


@router.post("/register", response_model=LoginResponse)
async def register(request: UserRegisterRequest):
    """用户注册"""
    service = get_user_service()
    
    user = service.register(
        username=request.username,
        password=request.password,
        display_name=request.display_name
    )
    
    if not user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 注册后自动登录
    result = service.login(request.username, request.password)
    if not result:
        raise HTTPException(status_code=500, detail="注册成功但登录失败")
    
    token, user = result
    
    return LoginResponse(
        token=token,
        user=service.to_response(user)
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: UserLoginRequest):
    """用户登录"""
    service = get_user_service()
    
    result = service.login(request.username, request.password)
    
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    token, user = result
    
    return LoginResponse(
        token=token,
        user=service.to_response(user)
    )


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """用户登出"""
    if not authorization:
        return {"success": True}
    
    # 解析 Bearer token
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    service = get_user_service()
    service.logout(token)
    
    return {"success": True}


@router.get("/me", response_model=UserResponse)
async def get_current_user(authorization: Optional[str] = Header(None)):
    """获取当前登录用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    
    # 解析 Bearer token
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    service = get_user_service()
    user = service.get_user_by_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    
    return service.to_response(user)

