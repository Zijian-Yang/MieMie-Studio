#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通义万相文生图节点
实现异步调用，返回生成的图片URL
"""

import json
from http import HTTPStatus
from typing import List, Optional
import dashscope
from dashscope import ImageSynthesis


class Text2ImageGenerator:
    """文生图生成器"""
    
    def __init__(self, config_path: str = "t2i_config.json"):
        """
        初始化生成器
        
        Args:
            config_path: 配置文件路径
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.api_key = self.config['dashscope_api_key']
        
        # 设置API基础URL（根据地域不同）
        base_url = self.config.get('base_url', 'https://dashscope.aliyuncs.com/api/v1')
        dashscope.base_http_api_url = base_url
        
    def create_task(self, prompt: Optional[str] = None):
        """
        创建文生图任务
        
        Args:
            prompt: 提示词，如果不提供则使用配置文件中的提示词
            
        Returns:
            task对象
        """
        # 准备参数
        params = {
            'api_key': self.api_key,
            'model': self.config['model'],
            'prompt': prompt or self.config['prompt'],
            'n': self.config['n'],
            'size': self.config['size'],
            'prompt_extend': self.config['prompt_extend'],
            'watermark': self.config['watermark']
        }
        
        # 如果设置了反向提示词，添加到参数中
        if self.config.get('negative_prompt'):
            params['negative_prompt'] = self.config['negative_prompt']
        
        # 如果配置了seed，添加到参数中
        if self.config.get('seed') is not None:
            params['seed'] = self.config['seed']
        
        # 发送创建任务请求
        print(f"正在创建文生图任务...")
        print(f"提示词: {params['prompt']}")
        
        rsp = ImageSynthesis.async_call(**params)
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"创建任务失败: status_code={rsp.status_code}, code={rsp.code}, message={rsp.message}")
        
        print(f"任务创建成功，task_id: {rsp.output.task_id}")
        print(f"任务状态: {rsp.output.task_status}")
        
        return rsp
    
    def wait_for_task(self, task) -> List[str]:
        """
        等待任务完成并返回结果
        
        Args:
            task: 任务对象（从create_task返回）
            
        Returns:
            图片URL列表
        """
        print(f"开始等待任务完成...")
        
        rsp = ImageSynthesis.wait(task=task, api_key=self.api_key)
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"任务失败: status_code={rsp.status_code}, code={rsp.code}, message={rsp.message}")
        
        task_status = rsp.output.task_status
        print(f"任务状态: {task_status}")
        
        if task_status == 'SUCCEEDED':
            # 任务成功，提取图片URL
            urls = []
            for result in rsp.output.results:
                urls.append(result.url)
                print(f"原始提示词: {result.orig_prompt}")
                # actual_prompt 仅在开启 prompt_extend 时返回
                try:
                    if result.actual_prompt:
                        print(f"实际提示词: {result.actual_prompt}")
                except (AttributeError, KeyError):
                    pass  # actual_prompt 字段不存在，跳过
                print(f"图片URL: {result.url}")
            
            print(f"任务完成，共生成 {len(urls)} 张图片")
            return urls
        
        elif task_status == 'FAILED':
            # 任务失败
            error_msg = getattr(rsp.output, 'message', '未知错误')
            raise Exception(f"任务失败: {error_msg}")
        
        else:
            raise Exception(f"未知的任务状态: {task_status}")
    
    def generate(self, prompt: Optional[str] = None) -> List[str]:
        """
        生成图片（完整流程）
        
        Args:
            prompt: 提示词，如果不提供则使用配置文件中的提示词
            
        Returns:
            图片URL列表
        """
        # 创建任务
        task = self.create_task(prompt)
        
        # 等待任务完成并返回结果
        urls = self.wait_for_task(task)
        
        return urls
    
    def generate_batch(self, prompts: List[str]) -> List[str]:
        """
        批量生成图片
        
        Args:
            prompts: 提示词数组
            
        Returns:
            URL数组，按提示词顺序返回，每个提示词生成的第一张图片URL
            如果某个提示词生成失败，对应位置返回空字符串""
        """
        if not prompts:
            return []
        
        results = []
        total = len(prompts)
        
        for i, prompt in enumerate(prompts, 1):
            print(f"\n{'='*50}")
            print(f"[{i}/{total}] 处理提示词: {prompt}")
            print(f"{'='*50}")
            
            try:
                urls = self.generate(prompt=prompt)
                # 取第一张图片URL
                if urls:
                    results.append(urls[0])
                else:
                    print(f"警告: 提示词 '{prompt}' 未生成任何图片")
                    results.append("")
            except Exception as e:
                print(f"错误: 提示词 '{prompt}' 生成失败: {str(e)}")
                # 失败时返回空字符串
                results.append("")
        
        print(f"\n{'='*50}")
        print(f"批量生成完成，共处理 {total} 个提示词")
        success_count = sum(1 for url in results if url)
        print(f"成功: {success_count}, 失败: {total - success_count}")
        print(f"{'='*50}\n")
        
        return results


def generate_images(prompts: List[str], config_path: str = "t2i_config.json") -> List[str]:
    """
    批量生成图片（便捷函数）
    
    Args:
        prompts: 提示词数组
        config_path: 配置文件路径，默认为 "t2i_config.json"
        
    Returns:
        URL数组，按提示词顺序返回，每个提示词生成的第一张图片URL
        如果某个提示词生成失败，对应位置返回空字符串""
        
    Example:
        >>> from text_to_image import generate_images
        >>> urls = generate_images(["一只可爱的猫", "一只快乐的狗"])
        >>> print(urls)
        ['https://...cat.png', 'https://...dog.png']
    """
    generator = Text2ImageGenerator(config_path=config_path)
    return generator.generate_batch(prompts)


def generate_image(prompt: str, config_path: str = "t2i_config.json") -> str:
    """
    生成单张图片（便捷函数）
    
    Args:
        prompt: 提示词
        config_path: 配置文件路径，默认为 "t2i_config.json"
        
    Returns:
        图片URL（第一张），如果失败返回空字符串""
        
    Example:
        >>> from text_to_image import generate_image
        >>> url = generate_image("一只可爱的猫")
        >>> print(url)
        'https://...cat.png'
    """
    generator = Text2ImageGenerator(config_path=config_path)
    urls = generator.generate(prompt=prompt)
    return urls[0] if urls else ""


def main():
    """主函数示例"""
    try:
        # 创建生成器实例
        generator = Text2ImageGenerator("t2i_config.json")
        
        # 生成图片（使用配置文件中的提示词）
        urls = generator.generate()
        
        print("\n" + "="*50)
        print("生成完成！图片URL:")
        for i, url in enumerate(urls, 1):
            print(f"{i}. {url}")
        print("="*50)
        
        return urls
        
    except Exception as e:
        print(f"错误: {str(e)}")
        raise


if __name__ == "__main__":
    main()

