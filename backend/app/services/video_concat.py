"""
视频拼接服务

使用 FFmpeg 将多个视频按顺序拼接成一个完整视频。
"""

import os
import subprocess
import tempfile
import uuid
from typing import List, Optional, Tuple
import httpx
import json


class VideoConcatService:
    """视频拼接服务"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        # 统一的输出参数
        self.target_fps = 30
        self.target_width = 1920
        self.target_height = 1080
    
    def check_ffmpeg(self) -> bool:
        """检查 FFmpeg 是否可用"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def get_video_info(self, video_path: str) -> dict:
        """获取视频信息"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-show_format',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            print(f"[视频信息] 获取失败: {e}")
        return {}
    
    def has_audio_stream(self, video_path: str) -> bool:
        """检查视频是否有音频流"""
        info = self.get_video_info(video_path)
        streams = info.get('streams', [])
        for stream in streams:
            if stream.get('codec_type') == 'audio':
                return True
        return False
    
    async def download_video(self, url: str, output_path: str) -> bool:
        """下载视频到本地"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(url, follow_redirects=True)
                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    return True
                else:
                    print(f"[视频下载] 失败: {url}, 状态码: {response.status_code}")
                    return False
        except Exception as e:
            print(f"[视频下载] 异常: {url}, 错误: {e}")
            return False
    
    def normalize_video(self, input_path: str, output_path: str, has_audio: bool) -> bool:
        """
        标准化视频：统一帧率、分辨率、编码
        
        这是解决音画不同步的关键步骤
        """
        print(f"[视频标准化] 处理: {os.path.basename(input_path)}")
        
        # 获取原视频信息
        info = self.get_video_info(input_path)
        streams = info.get('streams', [])
        
        # 找到视频流获取原始分辨率
        video_stream = None
        for stream in streams:
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break
        
        if video_stream:
            orig_width = int(video_stream.get('width', 1920))
            orig_height = int(video_stream.get('height', 1080))
            # 保持原始分辨率，但确保是偶数（FFmpeg 要求）
            target_w = orig_width if orig_width % 2 == 0 else orig_width + 1
            target_h = orig_height if orig_height % 2 == 0 else orig_height + 1
        else:
            target_w = self.target_width
            target_h = self.target_height
        
        # 构建 FFmpeg 命令
        # 关键：使用 fps 滤镜统一帧率，使用 scale 确保分辨率一致
        video_filter = f"fps={self.target_fps},scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2"
        
        if has_audio:
            cmd = [
                'ffmpeg',
                '-y',
                '-i', input_path,
                '-vf', video_filter,
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-r', str(self.target_fps),  # 强制输出帧率
                '-c:a', 'aac',
                '-ar', '44100',  # 统一音频采样率
                '-ac', '2',  # 统一为立体声
                '-b:a', '128k',
                '-shortest',  # 以最短的流为准
                output_path
            ]
        else:
            # 没有音频，添加静音音轨（确保所有视频都有音频，方便拼接）
            cmd = [
                'ffmpeg',
                '-y',
                '-i', input_path,
                '-f', 'lavfi',
                '-i', 'anullsrc=r=44100:cl=stereo',
                '-vf', video_filter,
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-r', str(self.target_fps),
                '-c:a', 'aac',
                '-ar', '44100',
                '-ac', '2',
                '-b:a', '128k',
                '-shortest',
                '-map', '0:v:0',
                '-map', '1:a:0',
                output_path
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"[视频标准化] 失败: {result.stderr[:500]}")
            return False
        
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    
    async def concat_videos(
        self,
        video_urls: List[str],
        output_filename: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        拼接多个视频
        
        流程：
        1. 下载所有视频
        2. 标准化所有视频（统一帧率、编码）
        3. 使用 concat demuxer 拼接（因为已经统一格式，可以安全使用）
        
        Args:
            video_urls: 视频URL列表（按顺序）
            output_filename: 输出文件名（可选）
        
        Returns:
            (成功标志, 输出文件路径或错误信息)
        """
        if not self.check_ffmpeg():
            return False, "FFmpeg 未安装或不可用"
        
        if not video_urls:
            return False, "没有视频需要拼接"
        
        # 创建临时目录
        work_dir = os.path.join(self.temp_dir, f"concat_{uuid.uuid4().hex}")
        os.makedirs(work_dir, exist_ok=True)
        
        downloaded_files = []
        normalized_files = []
        
        try:
            # 步骤 1：下载所有视频
            print(f"\n{'='*60}")
            print(f"步骤 1/3: 下载视频")
            print(f"{'='*60}")
            
            for i, url in enumerate(video_urls):
                local_path = os.path.join(work_dir, f"original_{i:03d}.mp4")
                print(f"[下载] {i+1}/{len(video_urls)}: {url[:80]}...")
                
                if await self.download_video(url, local_path):
                    downloaded_files.append(local_path)
                else:
                    return False, f"下载第 {i+1} 个视频失败"
            
            # 如果只有一个视频，跳过拼接直接返回
            if len(downloaded_files) == 1:
                print("[视频拼接] 只有一个视频，跳过拼接")
                return True, downloaded_files[0]
            
            # 步骤 2：标准化所有视频
            print(f"\n{'='*60}")
            print(f"步骤 2/3: 标准化视频（统一帧率、编码）")
            print(f"{'='*60}")
            
            for i, original_path in enumerate(downloaded_files):
                normalized_path = os.path.join(work_dir, f"normalized_{i:03d}.mp4")
                has_audio = self.has_audio_stream(original_path)
                print(f"[标准化] {i+1}/{len(downloaded_files)}, 有音频: {has_audio}")
                
                if self.normalize_video(original_path, normalized_path, has_audio):
                    normalized_files.append(normalized_path)
                else:
                    return False, f"标准化第 {i+1} 个视频失败"
            
            # 步骤 3：拼接视频
            print(f"\n{'='*60}")
            print(f"步骤 3/3: 拼接视频")
            print(f"{'='*60}")
            
            # 创建文件列表
            list_file = os.path.join(work_dir, "files.txt")
            with open(list_file, 'w') as f:
                for file_path in normalized_files:
                    escaped_path = file_path.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            # 输出文件路径
            if output_filename:
                output_path = os.path.join(work_dir, output_filename)
            else:
                output_path = os.path.join(work_dir, f"output_{uuid.uuid4().hex}.mp4")
            
            # 使用 concat demuxer 拼接（因为视频已经标准化，可以安全使用 -c copy）
            cmd = [
                'ffmpeg',
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                output_path
            ]
            
            print(f"[拼接] 合并 {len(normalized_files)} 个视频...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"[拼接] concat demuxer 失败，尝试重新编码拼接...")
                
                # 如果 copy 失败，使用重新编码方式
                inputs = []
                filter_parts = []
                for i, file_path in enumerate(normalized_files):
                    inputs.extend(['-i', file_path])
                    filter_parts.append(f'[{i}:v:0][{i}:a:0]')
                
                filter_str = ''.join(filter_parts) + f'concat=n={len(normalized_files)}:v=1:a=1[outv][outa]'
                
                cmd = [
                    'ffmpeg',
                    '-y',
                    *inputs,
                    '-filter_complex', filter_str,
                    '-map', '[outv]',
                    '-map', '[outa]',
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"[拼接] 失败: {result.stderr[:500]}")
                    return False, f"视频拼接失败: {result.stderr[:200]}"
            
            # 检查输出文件
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                file_size = os.path.getsize(output_path) / 1024 / 1024
                print(f"\n{'='*60}")
                print(f"拼接成功！")
                print(f"输出文件: {output_path}")
                print(f"文件大小: {file_size:.2f} MB")
                print(f"{'='*60}\n")
                return True, output_path
            else:
                return False, "输出文件不存在或为空"
            
        except Exception as e:
            print(f"[视频拼接] 异常: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
        
        finally:
            # 清理临时文件（保留输出文件）
            for file_path in downloaded_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
            for file_path in normalized_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
            try:
                list_file = os.path.join(work_dir, "files.txt")
                if os.path.exists(list_file):
                    os.remove(list_file)
            except:
                pass


# 全局实例
video_concat_service = VideoConcatService()
