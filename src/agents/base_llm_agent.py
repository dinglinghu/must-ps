"""
基础LLM智能体
使用LiteLLM提供统一的大模型接口，兼容ADK框架
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from abc import ABC, abstractmethod

# ADK框架导入
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.genai import types

logger = logging.getLogger(__name__)


class BaseLLMAgent(BaseAgent):
    """
    基础LLM智能体
    使用LiteLLM提供统一的大模型接口，兼容ADK框架
    """
    
    def __init__(
        self,
        name: str,
        model: str,
        instruction: str,
        description: str = "",
        tools: Optional[List] = None,
        llm_client=None
    ):
        """
        初始化基础LLM智能体
        
        Args:
            name: 智能体名称
            model: 模型名称
            instruction: 系统指令
            description: 智能体描述
            tools: 工具列表
            llm_client: LiteLLM客户端
        """
        super().__init__(name=name, description=description)
        
        self.model = model
        self.instruction = instruction
        self.tools = tools or []
        self.llm_client = llm_client
        
        # 对话历史
        self.conversation_history = []
        
        logger.info(f"✅ 基础LLM智能体 {name} 初始化完成")
    
    def set_llm_client(self, llm_client):
        """设置LLM客户端"""
        self.llm_client = llm_client
        logger.info(f"✅ 设置LLM客户端: {self.model}")
    
    async def generate_response(
        self,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        include_history: bool = True
    ) -> str:
        """
        生成响应
        
        Args:
            user_message: 用户消息
            temperature: 温度参数
            max_tokens: 最大令牌数
            include_history: 是否包含对话历史
            
        Returns:
            生成的响应
        """
        if not self.llm_client:
            raise ValueError("LLM客户端未设置")
        
        try:
            # 构建消息列表
            messages = [{"role": "system", "content": self.instruction}]
            
            # 添加对话历史
            if include_history and self.conversation_history:
                messages.extend(self.conversation_history[-10:])  # 只保留最近10轮对话
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": user_message})
            
            # 调用LLM
            response = await self.llm_client.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 提取响应内容
            if hasattr(response, 'choices') and len(response.choices) > 0:
                content = response.choices[0].message.content
                
                # 更新对话历史
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": content})
                
                # 限制历史长度
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
                return content
            else:
                logger.error(f"❌ 响应格式异常: {response}")
                return "响应格式异常"
                
        except Exception as e:
            logger.error(f"❌ 生成响应失败: {e}")
            return f"生成响应失败: {e}"
    
    async def generate_response_stream(
        self,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        include_history: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        流式生成响应
        
        Args:
            user_message: 用户消息
            temperature: 温度参数
            max_tokens: 最大令牌数
            include_history: 是否包含对话历史
            
        Yields:
            流式响应片段
        """
        if not self.llm_client:
            raise ValueError("LLM客户端未设置")
        
        try:
            # 构建消息列表
            messages = [{"role": "system", "content": self.instruction}]
            
            # 添加对话历史
            if include_history and self.conversation_history:
                messages.extend(self.conversation_history[-10:])
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": user_message})
            
            # 流式调用LLM
            full_response = ""
            async for chunk in await self.llm_client.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            ):
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        content = delta.content
                        full_response += content
                        yield content
            
            # 更新对话历史
            if full_response:
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": full_response})
                
                # 限制历史长度
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                    
        except Exception as e:
            logger.error(f"❌ 流式生成响应失败: {e}")
            yield f"流式生成响应失败: {e}"
    
    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
        logger.info(f"✅ 清除智能体 {self.name} 的对话历史")
    
    def get_history_summary(self) -> str:
        """获取对话历史摘要"""
        if not self.conversation_history:
            return "无对话历史"
        
        total_messages = len(self.conversation_history)
        user_messages = len([msg for msg in self.conversation_history if msg["role"] == "user"])
        assistant_messages = len([msg for msg in self.conversation_history if msg["role"] == "assistant"])
        
        return f"对话历史: {total_messages}条消息 (用户: {user_messages}, 助手: {assistant_messages})"
    
    async def process_message(self, message: str) -> AsyncGenerator[Event, None]:
        """
        处理消息（ADK兼容接口）
        
        Args:
            message: 输入消息
            
        Yields:
            ADK事件
        """
        try:
            # 生成响应
            response = await self.generate_response(message)
            
            # 创建ADK事件
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=response)])
            )
            
        except Exception as e:
            logger.error(f"❌ 处理消息失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"处理消息失败: {e}")])
            )
    
    async def process_message_stream(self, message: str) -> AsyncGenerator[Event, None]:
        """
        流式处理消息（ADK兼容接口）
        
        Args:
            message: 输入消息
            
        Yields:
            ADK事件流
        """
        try:
            # 流式生成响应
            async for chunk in self.generate_response_stream(message):
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=chunk)])
                )
                
        except Exception as e:
            logger.error(f"❌ 流式处理消息失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"流式处理消息失败: {e}")])
            )
    
    @abstractmethod
    async def run(self, *args, **kwargs) -> AsyncGenerator[Event, None]:
        """
        运行智能体（子类必须实现）
        
        Yields:
            ADK事件流
        """
        pass
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"BaseLLMAgent(name={self.name}, model={self.model})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"BaseLLMAgent(name={self.name}, model={self.model}, tools={len(self.tools)})"
