"""
DeepSeek API适配器
为ADK框架提供DeepSeek API支持
"""

import logging
import os
import json
from typing import Dict, List, Any, Optional, AsyncGenerator
import asyncio
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """DeepSeek API客户端"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1"):
        """
        初始化DeepSeek客户端
        
        Args:
            api_key: DeepSeek API密钥
            base_url: API基础URL
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用DeepSeek Chat Completion API
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大令牌数
            stream: 是否流式输出
            **kwargs: 其他参数
            
        Returns:
            API响应
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            **kwargs
        }
        
        try:
            url = f"{self.base_url}/chat/completions"
            logger.debug(f"🔗 调用DeepSeek API: {url}")
            logger.debug(f"📝 请求参数: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.debug(f"✅ DeepSeek API调用成功")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"❌ DeepSeek API调用失败: {response.status} - {error_text}")
                    raise Exception(f"DeepSeek API错误: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"❌ DeepSeek API调用异常: {e}")
            raise
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式调用DeepSeek Chat Completion API
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大令牌数
            **kwargs: 其他参数
            
        Yields:
            流式响应数据
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs
        }
        
        try:
            url = f"{self.base_url}/chat/completions"
            logger.debug(f"🔗 流式调用DeepSeek API: {url}")
            
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data = line[6:]  # 移除 'data: ' 前缀
                            if data == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                yield chunk
                            except json.JSONDecodeError:
                                continue
                else:
                    error_text = await response.text()
                    logger.error(f"❌ DeepSeek流式API调用失败: {response.status} - {error_text}")
                    raise Exception(f"DeepSeek API错误: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"❌ DeepSeek流式API调用异常: {e}")
            raise


class DeepSeekADKAdapter:
    """DeepSeek到ADK的适配器"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1"):
        """
        初始化适配器
        
        Args:
            api_key: DeepSeek API密钥
            base_url: API基础URL
        """
        self.client = DeepSeekClient(api_key, base_url)
        
    async def generate_response(
        self,
        instruction: str,
        user_message: str,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """
        生成响应（兼容ADK接口）
        
        Args:
            instruction: 系统指令
            user_message: 用户消息
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大令牌数
            
        Returns:
            生成的响应文本
        """
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": user_message}
        ]
        
        try:
            async with self.client:
                response = await self.client.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if 'choices' in response and len(response['choices']) > 0:
                    content = response['choices'][0]['message']['content']
                    logger.info(f"✅ DeepSeek响应生成成功，长度: {len(content)}")
                    return content
                else:
                    logger.error(f"❌ DeepSeek响应格式异常: {response}")
                    return "DeepSeek响应格式异常"
                    
        except Exception as e:
            logger.error(f"❌ DeepSeek响应生成失败: {e}")
            return f"DeepSeek调用失败: {e}"
    
    async def generate_response_stream(
        self,
        instruction: str,
        user_message: str,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> AsyncGenerator[str, None]:
        """
        流式生成响应（兼容ADK接口）
        
        Args:
            instruction: 系统指令
            user_message: 用户消息
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大令牌数
            
        Yields:
            流式响应文本片段
        """
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": user_message}
        ]
        
        try:
            async with self.client:
                async for chunk in self.client.chat_completion_stream(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                    if 'choices' in chunk and len(chunk['choices']) > 0:
                        delta = chunk['choices'][0].get('delta', {})
                        if 'content' in delta:
                            yield delta['content']
                            
        except Exception as e:
            logger.error(f"❌ DeepSeek流式响应生成失败: {e}")
            yield f"DeepSeek流式调用失败: {e}"


def create_deepseek_adapter(config: Dict[str, Any]) -> DeepSeekADKAdapter:
    """
    创建DeepSeek适配器
    
    Args:
        config: 配置字典，包含api_key和base_url
        
    Returns:
        DeepSeekADKAdapter实例
    """
    api_key = config.get('api_key')
    if not api_key:
        api_key_env = config.get('api_key_env')
        if api_key_env:
            api_key = os.getenv(api_key_env)
    
    if not api_key:
        raise ValueError("DeepSeek API密钥未配置")
    
    base_url = config.get('base_url', "https://api.deepseek.com/v1")
    
    logger.info(f"✅ 创建DeepSeek适配器: {base_url}")
    return DeepSeekADKAdapter(api_key, base_url)
