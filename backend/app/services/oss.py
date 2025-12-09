"""
阿里云 OSS 存储服务
用于将生成的图片和视频持久化存储到 OSS
"""
# OSS 服务已启用

import os
import uuid
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False

from app.config import get_config, OSSConfig


class OSSService:
    """OSS 存储服务"""
    
    def __init__(self):
        self._auth = None
        self._bucket = None
        self._config: Optional[OSSConfig] = None
    
    def _get_config(self) -> OSSConfig:
        """获取 OSS 配置"""
        return get_config().oss
    
    def _init_client(self) -> bool:
        """初始化 OSS 客户端"""
        if not OSS_AVAILABLE:
            print("警告: oss2 库未安装，OSS 功能不可用。请运行: pip install oss2")
            return False
        
        config = self._get_config()
        
        if not config.enabled:
            return False
        
        if not all([config.access_key_id, config.access_key_secret, config.bucket_name, config.endpoint]):
            print("警告: OSS 配置不完整")
            return False
        
        try:
            self._auth = oss2.Auth(config.access_key_id, config.access_key_secret)
            self._bucket = oss2.Bucket(self._auth, config.endpoint_url, config.bucket_name)
            self._config = config
            return True
        except Exception as e:
            print(f"OSS 客户端初始化失败: {e}")
            return False
    
    def is_enabled(self) -> bool:
        """检查 OSS 是否启用且配置正确"""
        config = self._get_config()
        return (
            OSS_AVAILABLE and 
            config.enabled and 
            bool(config.access_key_id) and 
            bool(config.access_key_secret) and 
            bool(config.bucket_name)
        )
    
    def _generate_object_key(self, file_type: str, extension: str, project_id: str = "") -> str:
        """
        生成 OSS 对象键
        
        Args:
            file_type: 文件类型 (image/video/audio)
            extension: 文件扩展名 (png/jpg/mp4)
            project_id: 项目ID（可选）
        
        Returns:
            OSS 对象键，格式: prefix/type/date/uuid.ext
        """
        config = self._get_config()
        prefix = config.prefix.rstrip('/')
        date_str = datetime.now().strftime('%Y%m%d')
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime('%H%M%S')
        
        if project_id:
            return f"{prefix}/{file_type}/{project_id}/{date_str}/{timestamp}_{unique_id}.{extension}"
        else:
            return f"{prefix}/{file_type}/{date_str}/{timestamp}_{unique_id}.{extension}"
    
    def upload_from_url(
        self, 
        url: str, 
        file_type: str = "image", 
        extension: str = "png",
        project_id: str = ""
    ) -> Tuple[bool, str]:
        """
        从 URL 下载文件并上传到 OSS
        
        Args:
            url: 原始文件 URL
            file_type: 文件类型
            extension: 文件扩展名
            project_id: 项目ID
        
        Returns:
            (success, url_or_error): 成功时返回 OSS URL，失败时返回错误信息
        """
        if not self.is_enabled():
            # OSS 未启用，返回原始 URL
            return True, url
        
        if not self._init_client():
            return False, "OSS 初始化失败"
        
        try:
            # 下载文件
            response = requests.get(url, timeout=60)
            if response.status_code != 200:
                return False, f"下载文件失败: HTTP {response.status_code}"
            
            # 根据 Content-Type 自动判断扩展名
            content_type = response.headers.get('Content-Type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                extension = 'jpg'
            elif 'png' in content_type:
                extension = 'png'
            elif 'webp' in content_type:
                extension = 'webp'
            elif 'mp4' in content_type:
                extension = 'mp4'
            elif 'video' in content_type:
                extension = 'mp4'
            
            # 生成对象键
            object_key = self._generate_object_key(file_type, extension, project_id)
            
            # 上传到 OSS
            result = self._bucket.put_object(object_key, response.content)
            
            if result.status == 200:
                # 构建公开访问 URL
                config = self._get_config()
                oss_url = f"https://{config.bucket_name}.{config.endpoint_host}/{object_key}"
                return True, oss_url
            else:
                return False, f"上传失败: HTTP {result.status}"
                
        except requests.exceptions.Timeout:
            return False, "下载超时"
        except requests.exceptions.RequestException as e:
            return False, f"下载失败: {str(e)}"
        except Exception as e:
            return False, f"上传失败: {str(e)}"
    
    def upload_from_bytes(
        self, 
        data: bytes, 
        file_type: str = "image", 
        extension: str = "png",
        project_id: str = ""
    ) -> Tuple[bool, str]:
        """
        上传字节数据到 OSS
        
        Args:
            data: 文件字节数据
            file_type: 文件类型
            extension: 文件扩展名
            project_id: 项目ID
        
        Returns:
            (success, url_or_error): 成功时返回 OSS URL，失败时返回错误信息
        """
        if not self.is_enabled():
            return False, "OSS 未启用"
        
        if not self._init_client():
            return False, "OSS 初始化失败"
        
        try:
            object_key = self._generate_object_key(file_type, extension, project_id)
            result = self._bucket.put_object(object_key, data)
            
            if result.status == 200:
                config = self._get_config()
                oss_url = f"https://{config.bucket_name}.{config.endpoint_host}/{object_key}"
                return True, oss_url
            else:
                return False, f"上传失败: HTTP {result.status}"
                
        except Exception as e:
            return False, f"上传失败: {str(e)}"
    
    def upload_image(self, url: str, project_id: str = "") -> str:
        """
        上传图片到 OSS，返回持久化 URL
        如果 OSS 未启用或上传失败，返回原始 URL
        
        Args:
            url: 原始图片 URL
            project_id: 项目ID
        
        Returns:
            持久化后的图片 URL
        """
        success, result = self.upload_from_url(url, "image", "png", project_id)
        if success:
            return result
        else:
            print(f"图片上传到 OSS 失败: {result}，使用原始 URL")
            return url
    
    def upload_video(self, url: str, project_id: str = "") -> str:
        """
        上传视频到 OSS，返回持久化 URL
        如果 OSS 未启用或上传失败，返回原始 URL
        
        Args:
            url: 原始视频 URL
            project_id: 项目ID
        
        Returns:
            持久化后的视频 URL
        """
        success, result = self.upload_from_url(url, "video", "mp4", project_id)
        if success:
            return result
        else:
            print(f"视频上传到 OSS 失败: {result}，使用原始 URL")
            return url
    
    def reinitialize(self):
        """
        重新初始化 OSS 服务
        当配置更新后调用此方法
        """
        self._auth = None
        self._bucket = None
        self._config = None
        print("OSS 服务已重置，将在下次使用时重新初始化")
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        测试 OSS 连接
        
        Returns:
            (success, message): 连接是否成功及消息
        """
        if not OSS_AVAILABLE:
            return False, "oss2 库未安装，请运行: pip install oss2"
        
        config = self._get_config()
        
        if not config.enabled:
            return False, "OSS 未启用"
        
        if not all([config.access_key_id, config.access_key_secret, config.bucket_name, config.endpoint]):
            return False, "OSS 配置不完整，请检查 AccessKey、Bucket名称和Endpoint"
        
        try:
            auth = oss2.Auth(config.access_key_id, config.access_key_secret)
            bucket = oss2.Bucket(auth, config.endpoint_url, config.bucket_name)
            
            # 尝试获取 bucket 信息来测试连接
            bucket.get_bucket_info()
            return True, "连接成功"
        except oss2.exceptions.NoSuchBucket:
            return False, f"Bucket '{config.bucket_name}' 不存在"
        except oss2.exceptions.AccessDenied:
            return False, "访问被拒绝，请检查 AccessKey 权限"
        except oss2.exceptions.ServerError as e:
            return False, f"服务器错误: {str(e)}"
        except Exception as e:
            return False, f"连接失败: {str(e)}"


# 全局 OSS 服务实例
oss_service = OSSService()

