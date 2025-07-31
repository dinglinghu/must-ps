"""
LiteLLM客户端
为ADK框架提供统一的大模型API接口，支持DeepSeek等多种模型
"""

import logging
import os
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import litellm
    from litellm import completion, acompletion
    LITELLM_AVAILABLE = True
    logger.info("✅ LiteLLM已导入")
except ImportError:
    LITELLM_AVAILABLE = False
    logger.warning("⚠️ LiteLLM未安装，请运行: pip install litellm")


class LiteLLMClient:
    """LiteLLM统一客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LiteLLM客户端
        
        Args:
            config: 配置字典
        """
        if not LITELLM_AVAILABLE:
            raise ImportError("LiteLLM未安装，请运行: pip install litellm")
        
        self.config = config
        self.model = config.get('model', 'deepseek/deepseek-chat')
        self.api_key = self._get_api_key()
        self.base_url = config.get('base_url')
        
        # 设置LiteLLM配置
        self._setup_litellm()
        
        logger.info(f"✅ LiteLLM客户端初始化完成: {self.model}")
    
    def _get_api_key(self) -> Optional[str]:
        """获取API密钥"""
        # 优先使用直接配置的API密钥
        api_key = self.config.get('api_key')
        if api_key:
            return api_key
        
        # 从环境变量获取
        api_key_env = self.config.get('api_key_env')
        if api_key_env:
            api_key = os.getenv(api_key_env)
            if api_key:
                return api_key
            else:
                logger.warning(f"⚠️ 环境变量 {api_key_env} 未设置")
        
        return None
    
    def _setup_litellm(self):
        """设置LiteLLM配置"""
        try:
            # 设置API密钥
            if self.api_key:
                if self.model.startswith('deepseek/'):
                    os.environ['DEEPSEEK_API_KEY'] = self.api_key
                    logger.info("✅ 设置DeepSeek API密钥")
                elif self.model.startswith('openai/') or 'gpt' in self.model:
                    os.environ['OPENAI_API_KEY'] = self.api_key
                    logger.info("✅ 设置OpenAI API密钥")
            
            # 设置基础URL（如果需要）
            if self.base_url:
                litellm.api_base = self.base_url
                logger.info(f"✅ 设置API基础URL: {self.base_url}")
            
            # 设置日志级别
            litellm.set_verbose = False  # 减少日志输出
            
        except Exception as e:
            logger.error(f"❌ LiteLLM配置设置失败: {e}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        agent_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用聊天完成API
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大令牌数
            stream: 是否流式输出
            **kwargs: 其他参数
            
        Returns:
            API响应
        """
        try:
            # 准备参数
            params = {
                'model': self.model,
                'messages': messages,
                'temperature': temperature or self.config.get('temperature', 0.7),
                'max_tokens': max_tokens or self.config.get('max_tokens', 4096),
                'stream': stream,
                **kwargs
            }
            
            # 移除None值
            params = {k: v for k, v in params.items() if v is not None}

            # 构建智能体信息
            agent_info = f" (Agent: {agent_name})" if agent_name else ""

            logger.info(f"🔗 LiteLLM API调用{agent_info}: {self.model}")
            logger.debug(f"📝 消息数量: {len(messages)}")

            # 调用LiteLLM
            if stream:
                return await self._stream_completion(params, agent_name)
            else:
                response = await acompletion(**params)
                logger.info(f"✅ LiteLLM API调用成功{agent_info}: {self.model}")
                return response
                
        except Exception as e:
            logger.error(f"❌ LiteLLM API调用失败: {e}")
            raise
    
    async def _stream_completion(self, params: Dict[str, Any], agent_name: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """流式完成"""
        try:
            response = await acompletion(**params)
            async for chunk in response:
                yield chunk
        except Exception as e:
            logger.error(f"❌ LiteLLM流式API调用失败: {e}")
            raise
    
    async def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        agent_name: Optional[str] = None
    ) -> str:
        """
        生成响应（简化接口）
        
        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            temperature: 温度参数
            max_tokens: 最大令牌数
            
        Returns:
            生成的响应文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response = await self.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                agent_name=agent_name
            )
            
            if hasattr(response, 'choices') and len(response.choices) > 0:
                content = response.choices[0].message.content
                logger.info(f"✅ 响应生成成功，长度: {len(content)}")
                return content
            else:
                logger.error(f"❌ 响应格式异常: {response}")
                return "响应格式异常"
                
        except Exception as e:
            logger.error(f"❌ 响应生成失败: {e}")
            return f"调用失败: {e}"
    
    async def generate_response_stream(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成响应
        
        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            temperature: 温度参数
            max_tokens: 最大令牌数
            
        Yields:
            流式响应文本片段
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            async for chunk in await self.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            ):
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        yield delta.content
                        
        except Exception as e:
            logger.error(f"❌ 流式响应生成失败: {e}")
            yield f"流式调用失败: {e}"


def create_litellm_client(config: Dict[str, Any]) -> LiteLLMClient:
    """
    创建LiteLLM客户端
    
    Args:
        config: 配置字典
        
    Returns:
        LiteLLMClient实例
    """
    if not LITELLM_AVAILABLE:
        raise ImportError("LiteLLM未安装，请运行: pip install litellm")
    
    logger.info(f"✅ 创建LiteLLM客户端: {config.get('model', 'unknown')}")
    return LiteLLMClient(config)


def test_litellm_connection(config: Dict[str, Any]) -> bool:
    """
    测试LiteLLM连接
    
    Args:
        config: 配置字典
        
    Returns:
        连接是否成功
    """
    try:
        client = create_litellm_client(config)
        
        # 简单测试
        async def test():
            response = await client.generate_response(
                system_prompt="你是一个测试助手。",
                user_message="请回复'测试成功'",
                max_tokens=10
            )
            return "测试成功" in response or "success" in response.lower()
        
        result = asyncio.run(test())
        if result:
            logger.info("✅ LiteLLM连接测试成功")
        else:
            logger.warning("⚠️ LiteLLM连接测试失败")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ LiteLLM连接测试异常: {e}")
        return False
