"""
阿里云 OSS 存储服务
用于将生成的图片和视频持久化存储到 OSS
支持多用户独立 OSS 配置

注意：使用线程池执行 OSS 上传操作，避免在异步环境中的并发问题
"""

import os
import logging
import uuid
import hashlib
import httpx
import threading
import asyncio
from dataclasses import dataclass

logger = logging.getLogger(__name__)
from concurrent.futures import ThreadPoolExecutor
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

# 全局线程池，用于执行 OSS 上传操作
_oss_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="oss_upload")


@dataclass
class _StagedFile:
    path: Path
    local_url: str
    extension: str


class OSSService:
    """OSS 存储服务
    
    使用线程池执行 OSS 操作，避免 oss2 SDK 在异步环境中的连接问题
    """
    
    def __init__(self):
        self._auth = None
        self._bucket = None
        self._config: Optional[OSSConfig] = None
        self._lock = threading.Lock()  # 线程安全锁
    
    def _get_config(self) -> OSSConfig:
        """获取 OSS 配置（每次都从用户配置中获取，确保用户隔离）"""
        return get_config().oss
    
    def _init_client(self) -> Tuple[bool, Optional['oss2.Bucket']]:
        """
        初始化 OSS 客户端
        每次调用都重新创建，确保使用当前用户的配置
        
        Returns:
            (success, bucket): 成功时返回 bucket 对象
        """
        if not OSS_AVAILABLE:
            logger.warning("oss2 库未安装，OSS 功能不可用。请运行: pip install oss2")
            return False, None
        
        config = self._get_config()
        
        if not config.enabled:
            return False, None
        
        if not all([config.access_key_id, config.access_key_secret, config.bucket_name, config.endpoint]):
            logger.warning("OSS 配置不完整")
            return False, None
        
        try:
            auth = oss2.Auth(config.access_key_id, config.access_key_secret)
            # 创建独立的 bucket 实例，避免连接复用问题
            bucket = oss2.Bucket(auth, config.endpoint_url, config.bucket_name)
            return True, bucket
        except Exception as e:
            logger.error(f"OSS 客户端初始化失败: {e}")
            return False, None
    
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

    def _assets_dir(self) -> Path:
        """本地静态素材目录"""
        return Path(__file__).parent.parent.parent / "data" / "assets"

    def _safe_path_part(self, value: str, default: str) -> str:
        """生成安全的本地路径片段"""
        normalized = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value.strip())
        return normalized[:80] or default

    def _project_staging_part(self, project_id: str) -> str:
        if not project_id:
            return "_global"
        digest = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:16]
        return self._safe_path_part(project_id, digest)

    def _normalize_extension(self, extension: str) -> str:
        normalized = (extension or "").strip().lower().lstrip(".")
        if normalized == "jpeg":
            normalized = "jpg"
        if not normalized or any(not (ch.isalnum() or ch in {"_", "-"}) for ch in normalized):
            return "bin"
        return normalized[:12]

    def _extension_from_content_type(self, content_type: str, fallback: str) -> str:
        content_type = (content_type or "").lower()
        if "jpeg" in content_type or "jpg" in content_type:
            return "jpg"
        if "png" in content_type:
            return "png"
        if "webp" in content_type:
            return "webp"
        if "gif" in content_type:
            return "gif"
        if "mp4" in content_type or "video" in content_type:
            return "mp4"
        if "mpeg" in content_type:
            return "mp3"
        if "wav" in content_type:
            return "wav"
        return self._normalize_extension(fallback)

    def _build_staging_target(
        self,
        file_type: str,
        extension: str,
        project_id: str = "",
    ) -> tuple[Path, str]:
        """构造本地暂存文件路径和可访问 URL"""
        safe_file_type = self._safe_path_part(file_type, "file")
        safe_project = self._project_staging_part(project_id)
        date_str = datetime.now().strftime("%Y%m%d")
        timestamp = datetime.now().strftime("%H%M%S")
        unique_id = uuid.uuid4().hex[:12]
        safe_extension = self._normalize_extension(extension)
        relative_path = Path("oss_staging") / safe_file_type / safe_project / date_str / f"{timestamp}_{unique_id}.{safe_extension}"
        file_path = self._assets_dir() / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        local_url = "/" + str(Path("assets") / relative_path).replace(os.sep, "/")
        return file_path, local_url

    def _cleanup_staged_file(self, file_path: Path) -> None:
        """清理本地暂存文件，父目录为空时顺带清理"""
        try:
            file_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"[OSS] 清理本地暂存文件失败: {file_path} ({exc})")
            return

        assets_dir = self._assets_dir()
        current = file_path.parent
        while current != assets_dir and assets_dir in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    def _download_url_to_staging_sync(
        self,
        url: str,
        file_type: str = "image",
        extension: str = "png",
        project_id: str = "",
    ) -> Tuple[bool, str | _StagedFile]:
        """下载远程 URL 到本地暂存文件；仅在 OSS 启用链路中调用"""
        dl_timeout = httpx.Timeout(10.0, read=300.0) if file_type.startswith("video") else httpx.Timeout(60.0)
        staged_path: Optional[Path] = None

        try:
            with httpx.stream("GET", url, timeout=dl_timeout, follow_redirects=True) as response:
                if response.status_code != 200:
                    return False, f"下载文件失败: HTTP {response.status_code}"

                final_extension = self._extension_from_content_type(
                    response.headers.get("Content-Type", ""),
                    extension,
                )
                staged_path, local_url = self._build_staging_target(file_type, final_extension, project_id)
                with open(staged_path, "wb") as file:
                    for chunk in response.iter_bytes():
                        if chunk:
                            file.write(chunk)
                    file.flush()
                    os.fsync(file.fileno())

            if not staged_path or staged_path.stat().st_size <= 0:
                return False, "下载文件为空"

            return True, _StagedFile(
                path=staged_path,
                local_url=local_url,
                extension=final_extension,
            )
        except httpx.TimeoutException:
            logger.warning(f"[OSS] 下载超时 ({file_type}): {url[:120]}...")
            return False, f"下载超时（{file_type}）"
        except httpx.HTTPError as e:
            logger.error(f"[OSS] 下载失败 ({file_type}): {e}")
            return False, f"下载失败: {str(e)}"
        except OSError as e:
            logger.error(f"[OSS] 写入本地暂存失败 ({file_type}): {e}")
            return False, f"写入本地暂存失败: {str(e)}"
        finally:
            if staged_path and staged_path.exists() and staged_path.stat().st_size == 0:
                staged_path.unlink(missing_ok=True)

    def _upload_from_url_sync(
        self, 
        url: str, 
        file_type: str = "image", 
        extension: str = "png",
        project_id: str = ""
    ) -> Tuple[bool, str]:
        """
        同步方法：从 URL 下载文件并上传到 OSS
        此方法应在线程池中调用，避免阻塞异步事件循环
        
        Args:
            url: 原始文件 URL
            file_type: 文件类型
            extension: 文件扩展名
            project_id: 项目ID
        
        Returns:
            (success, url_or_error): 成功时返回 OSS URL，失败时返回错误信息
        """
        if not self.is_enabled():
            return True, url

        staged_success, staged_result = self._download_url_to_staging_sync(
            url,
            file_type,
            extension,
            project_id,
        )
        if not staged_success:
            return False, str(staged_result)
        staged_file = staged_result
        assert isinstance(staged_file, _StagedFile)

        with self._lock:
            success, bucket = self._init_client()
            if not success or bucket is None:
                return False, f"OSS 初始化失败，本地暂存: {staged_file.local_url}"
            
            try:
                object_key = self._generate_object_key(file_type, staged_file.extension, project_id)
                with open(staged_file.path, "rb") as file:
                    result = bucket.put_object(object_key, file)

                if result.status == 200:
                    config = self._get_config()
                    oss_url = f"https://{config.bucket_name}.{config.endpoint_host}/{object_key}"
                    logger.info(f"[OSS] 上传成功 ({file_type}): {oss_url}")
                    self._cleanup_staged_file(staged_file.path)
                    return True, oss_url
                else:
                    logger.error(f"[OSS] 上传失败: HTTP {result.status}")
                    return False, f"上传失败: HTTP {result.status}，本地暂存: {staged_file.local_url}"

            except Exception as e:
                logger.error(f"[OSS] 上传异常 ({file_type}): {e}")
                return False, f"上传失败: {str(e)}，本地暂存: {staged_file.local_url}"
    
    def upload_from_url(
        self, 
        url: str, 
        file_type: str = "image", 
        extension: str = "png",
        project_id: str = ""
    ) -> Tuple[bool, str]:
        """
        从 URL 下载文件并上传到 OSS（同步版本）
        
        Args:
            url: 原始文件 URL
            file_type: 文件类型
            extension: 文件扩展名
            project_id: 项目ID
        
        Returns:
            (success, url_or_error): 成功时返回 OSS URL，失败时返回错误信息
        """
        return self._upload_from_url_sync(url, file_type, extension, project_id)
    
    async def upload_from_url_async(
        self, 
        url: str, 
        file_type: str = "image", 
        extension: str = "png",
        project_id: str = ""
    ) -> Tuple[bool, str]:
        """
        异步方法：从 URL 下载文件并上传到 OSS
        使用线程池执行，避免阻塞异步事件循环和 oss2 SDK 的并发问题
        
        Args:
            url: 原始文件 URL
            file_type: 文件类型
            extension: 文件扩展名
            project_id: 项目ID
        
        Returns:
            (success, url_or_error): 成功时返回 OSS URL，失败时返回错误信息
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _oss_executor,
            self._upload_from_url_sync,
            url, file_type, extension, project_id
        )
    
    def _upload_from_bytes_sync(
        self, 
        data: bytes, 
        file_type: str = "image", 
        extension: str = "png",
        project_id: str = ""
    ) -> Tuple[bool, str]:
        """
        同步方法：上传字节数据到 OSS
        """
        if not self.is_enabled():
            return False, "OSS 未启用"
        
        with self._lock:
            success, bucket = self._init_client()
            if not success or bucket is None:
                return False, "OSS 初始化失败"
            
            try:
                object_key = self._generate_object_key(file_type, extension, project_id)
                result = bucket.put_object(object_key, data)
                
                if result.status == 200:
                    config = self._get_config()
                    oss_url = f"https://{config.bucket_name}.{config.endpoint_host}/{object_key}"
                    return True, oss_url
                else:
                    return False, f"上传失败: HTTP {result.status}"
                    
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
        上传字节数据到 OSS（同步版本）
        
        Args:
            data: 文件字节数据
            file_type: 文件类型
            extension: 文件扩展名
            project_id: 项目ID
        
        Returns:
            (success, url_or_error): 成功时返回 OSS URL，失败时返回错误信息
        """
        return self._upload_from_bytes_sync(data, file_type, extension, project_id)
    
    def _upload_bytes_sync(self, data: bytes, object_path: str) -> str:
        """
        同步方法：直接上传字节数据到指定OSS路径
        """
        if not self.is_enabled():
            raise Exception("OSS 未启用")
        
        with self._lock:
            success, bucket = self._init_client()
            if not success or bucket is None:
                raise Exception("OSS 初始化失败")
            
            try:
                config = self._get_config()
                prefix = config.prefix.rstrip('/')
                full_path = f"{prefix}/{object_path}"
                
                result = bucket.put_object(full_path, data)
                
                if result.status == 200:
                    oss_url = f"https://{config.bucket_name}.{config.endpoint_host}/{full_path}"
                    return oss_url
                else:
                    raise Exception(f"上传失败: HTTP {result.status}")
                    
            except Exception as e:
                raise Exception(f"上传失败: {str(e)}")
    
    def upload_bytes(self, data: bytes, object_path: str) -> str:
        """
        简化版：直接上传字节数据到指定OSS路径（同步版本）
        
        Args:
            data: 文件字节数据
            object_path: OSS对象路径（如 audio/project_id/filename.mp3）
        
        Returns:
            OSS URL，失败时抛出异常
        """
        return self._upload_bytes_sync(data, object_path)

    async def upload_bytes_async(self, data: bytes, object_path: str) -> str:
        """
        异步版：直接上传字节数据到指定OSS路径
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _oss_executor,
            self._upload_bytes_sync,
            data,
            object_path,
        )
    
    def upload_image(self, url: str, project_id: str = "") -> str:
        """
        上传图片到 OSS，返回持久化 URL（同步版本）
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
            logger.warning(f"图片上传到 OSS 失败: {result}，使用原始 URL")
            return url
    
    async def upload_image_async(self, url: str, project_id: str = "") -> str:
        """
        异步上传图片到 OSS，返回持久化 URL
        如果 OSS 未启用或上传失败，返回原始 URL
        
        推荐在异步环境中使用此方法，避免并发问题
        
        Args:
            url: 原始图片 URL
            project_id: 项目ID
        
        Returns:
            持久化后的图片 URL
        """
        success, result = await self.upload_from_url_async(url, "image", "png", project_id)
        if success:
            return result
        else:
            logger.warning(f"图片上传到 OSS 失败: {result}，使用原始 URL")
            return url
    
    def upload_video(self, url: str, project_id: str = "") -> str:
        """
        上传视频到 OSS，返回持久化 URL（同步版本）
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
            logger.warning(f"视频上传到 OSS 失败: {result}，使用原始 URL")
            return url
    
    async def upload_video_async(self, url: str, project_id: str = "") -> str:
        """
        异步上传视频到 OSS，返回持久化 URL
        如果 OSS 未启用或上传失败，返回原始 URL
        
        推荐在异步环境中使用此方法，避免并发问题
        
        Args:
            url: 原始视频 URL
            project_id: 项目ID
        
        Returns:
            持久化后的视频 URL
        """
        logger.info(f"[OSS] 开始上传视频到 OSS, project_id={project_id}, url={url[:100]}...")
        success, result = await self.upload_from_url_async(url, "video", "mp4", project_id)
        if success:
            return result
        else:
            logger.warning(f"[OSS] 视频上传到 OSS 失败: {result}，使用原始临时 URL（24小时后过期）")
            return url

    def is_current_oss_url(self, url: str) -> bool:
        """判断 URL 是否已经是当前用户配置的 OSS 链接"""
        if not url:
            return False
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False

        config = self._get_config()
        if not config.bucket_name or not config.endpoint_host:
            return False
        return parsed.netloc == f"{config.bucket_name}.{config.endpoint_host}"

    def should_rehost_remote_url(self, url: str) -> bool:
        """判断远程 URL 是否需要重托管到当前 OSS"""
        if not url or not self.is_enabled():
            return False
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        return not self.is_current_oss_url(url)

    def is_probably_temporary_url(self, url: str) -> bool:
        """判断 URL 是否像厂商返回的临时签名链接"""
        if not url:
            return False
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        query = parsed.query.lower()
        if host.startswith("dashscope-result-"):
            return True
        temporary_markers = (
            "expires=",
            "ossaccesskeyid=",
            "signature=",
            "x-oss-",
            "x-amz-",
        )
        return any(marker in query for marker in temporary_markers)

    def should_persist_generated_url(self, url: str) -> bool:
        """判断生成结果 URL 是否需要转存到当前 OSS"""
        return self.should_rehost_remote_url(url) and self.is_probably_temporary_url(url)

    def should_persist_remote_url(self, url: str) -> bool:
        """兼容旧调用：等价于 should_rehost_remote_url。"""
        return self.should_rehost_remote_url(url)

    async def _ensure_remote_url_persisted_async(
        self,
        url: str,
        file_type: str,
        extension: str,
        project_id: str = "",
        strict: bool = False,
        max_retries: int = 3,
    ) -> str:
        """将生成结果 URL 持久化到当前 OSS，可选择失败时抛错"""
        if not self.should_rehost_remote_url(url):
            return url

        last_error = ""
        attempts = max(1, max_retries)
        for attempt in range(attempts):
            success, result = await self.upload_from_url_async(url, file_type, extension, project_id)
            if success:
                return result
            last_error = result
            if attempt < attempts - 1:
                await asyncio.sleep(min(2 ** attempt, 8))

        message = f"{file_type} 结果转存 OSS 失败: {last_error or '未知错误'}"
        if strict:
            raise RuntimeError(message)
        logger.warning(f"[OSS] {message}，保留原始 URL: {url[:120]}...")
        return url

    async def ensure_image_persisted_async(
        self,
        url: str,
        project_id: str = "",
        strict: bool = False,
        max_retries: int = 3,
    ) -> str:
        """确保图片 URL 已转存到当前 OSS"""
        return await self._ensure_remote_url_persisted_async(
            url,
            "image",
            "png",
            project_id,
            strict,
            max_retries,
        )

    async def ensure_video_persisted_async(
        self,
        url: str,
        project_id: str = "",
        strict: bool = False,
        max_retries: int = 3,
    ) -> str:
        """确保视频 URL 已转存到当前 OSS"""
        return await self._ensure_remote_url_persisted_async(
            url,
            "video",
            "mp4",
            project_id,
            strict,
            max_retries,
        )
    
    def reinitialize(self):
        """
        重新初始化 OSS 服务
        当配置更新后调用此方法
        """
        self._auth = None
        self._bucket = None
        self._config = None
        logger.info("OSS 服务已重置，将在下次使用时重新初始化")
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        测试 OSS 连接
        
        通过上传并删除一个小测试文件来验证连接，
        这与实际使用场景（上传图片/视频）一致。
        
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
            
            # 尝试上传一个小测试文件
            prefix = config.prefix.rstrip('/')
            test_key = f"{prefix}/.connection_test"
            test_content = b"connection_test"
            
            # 上传测试文件
            result = bucket.put_object(test_key, test_content)
            
            if result.status == 200:
                # 上传成功，尝试删除测试文件（可选，失败不影响结果）
                try:
                    bucket.delete_object(test_key)
                except:
                    pass  # 删除失败不影响测试结果
                return True, "连接成功"
            else:
                return False, f"上传测试失败: HTTP {result.status}"
                
        except oss2.exceptions.NoSuchBucket:
            return False, f"Bucket '{config.bucket_name}' 不存在"
        except oss2.exceptions.AccessDenied:
            return False, "访问被拒绝，请检查 AccessKey 是否有写入权限"
        except oss2.exceptions.ServerError as e:
            return False, f"服务器错误: {str(e)}"
        except Exception as e:
            return False, f"连接失败: {str(e)}"


# 全局 OSS 服务实例
oss_service = OSSService()
