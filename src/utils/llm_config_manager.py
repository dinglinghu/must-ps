"""
大模型配置管理器
统一管理大模型配置、API密钥和智能体提示词
支持LiteLLM统一接口
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import yaml

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """大模型配置数据类"""
    provider: str
    model: str
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 1


@dataclass
class AgentPromptConfig:
    """智能体提示词配置数据类"""
    system_prompt: str
    user_prompt_template: str
    few_shot_examples: List[Dict[str, str]]


class LLMConfigManager:
    """大模型配置管理器"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.llm_config = self.config.get('llm', {})
        self.agent_prompts = self.config.get('agent_prompts', {})
        
        logger.info("🔧 大模型配置管理器初始化完成")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ 配置文件加载成功: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"❌ 配置文件加载失败: {e}")
            return {}
    
    def get_llm_config(self, agent_type: Optional[str] = None) -> LLMConfig:
        """
        获取大模型配置
        
        Args:
            agent_type: 智能体类型，如果指定则使用特定配置
            
        Returns:
            LLMConfig: 大模型配置对象
        """
        # 获取主要配置
        primary_config = self.llm_config.get('primary', {})
        
        # 如果指定了智能体类型，尝试获取特定配置
        if agent_type:
            agent_specific = self.llm_config.get('agent_specific', {})
            specific_config = agent_specific.get(agent_type, {})
            # 合并配置，特定配置覆盖默认配置
            primary_config = {**primary_config, **specific_config}
        
        # 处理API密钥
        api_key = primary_config.get('api_key')
        api_key_env = primary_config.get('api_key_env')
        
        if not api_key and api_key_env:
            api_key = os.getenv(api_key_env)
            if not api_key:
                logger.warning(f"⚠️ 环境变量 {api_key_env} 未设置")
        
        return LLMConfig(
            provider=primary_config.get('provider', 'google'),
            model=primary_config.get('model', 'gemini-2.0-flash'),
            api_key=api_key,
            api_key_env=api_key_env,
            base_url=primary_config.get('base_url'),
            api_version=primary_config.get('api_version'),
            max_tokens=primary_config.get('max_tokens', 4096),
            temperature=primary_config.get('temperature', 0.7),
            top_p=primary_config.get('top_p', 0.9),
            frequency_penalty=primary_config.get('frequency_penalty', 0.0),
            presence_penalty=primary_config.get('presence_penalty', 0.0),
            timeout=primary_config.get('timeout', 30),
            retry_attempts=primary_config.get('retry_attempts', 3),
            retry_delay=primary_config.get('retry_delay', 1)
        )
    
    def get_fallback_configs(self) -> List[LLMConfig]:
        """
        获取备用模型配置列表
        
        Returns:
            List[LLMConfig]: 备用模型配置列表
        """
        fallback_configs = []
        fallback_list = self.llm_config.get('fallback', [])
        
        for fallback in fallback_list:
            # 处理API密钥
            api_key = fallback.get('api_key')
            api_key_env = fallback.get('api_key_env')
            
            if not api_key and api_key_env:
                api_key = os.getenv(api_key_env)
            
            config = LLMConfig(
                provider=fallback.get('provider'),
                model=fallback.get('model'),
                api_key=api_key,
                api_key_env=api_key_env,
                base_url=fallback.get('base_url'),
                api_version=fallback.get('api_version'),
                max_tokens=fallback.get('max_tokens', 4096),
                temperature=fallback.get('temperature', 0.7),
                top_p=fallback.get('top_p', 0.9),
                frequency_penalty=fallback.get('frequency_penalty', 0.0),
                presence_penalty=fallback.get('presence_penalty', 0.0),
                timeout=fallback.get('timeout', 30),
                retry_attempts=fallback.get('retry_attempts', 3),
                retry_delay=fallback.get('retry_delay', 1)
            )
            fallback_configs.append(config)
        
        return fallback_configs
    
    def get_agent_prompt_config(self, agent_type: str) -> AgentPromptConfig:
        """
        获取智能体提示词配置
        
        Args:
            agent_type: 智能体类型
            
        Returns:
            AgentPromptConfig: 智能体提示词配置对象
        """
        prompt_config = self.agent_prompts.get(agent_type, {})
        
        if not prompt_config:
            logger.warning(f"⚠️ 未找到智能体类型 {agent_type} 的提示词配置")
            # 返回默认配置
            return AgentPromptConfig(
                system_prompt="你是一个专业的智能体，请协助完成任务。",
                user_prompt_template="任务: {task}",
                few_shot_examples=[]
            )
        
        return AgentPromptConfig(
            system_prompt=prompt_config.get('system_prompt', ''),
            user_prompt_template=prompt_config.get('user_prompt_template', ''),
            few_shot_examples=prompt_config.get('few_shot_examples', [])
        )
    
    def get_common_instructions(self) -> Dict[str, str]:
        """
        获取通用指令
        
        Returns:
            Dict[str, str]: 通用指令字典
        """
        common_config = self.agent_prompts.get('common', {})
        return {
            'global_instructions': common_config.get('global_instructions', ''),
            'error_handling': common_config.get('error_handling', ''),
            'collaboration': common_config.get('collaboration', ''),
            'security': common_config.get('security', '')
        }
    
    def format_system_prompt(self, agent_type: str, **kwargs) -> str:
        """
        格式化系统提示词
        
        Args:
            agent_type: 智能体类型
            **kwargs: 格式化参数
            
        Returns:
            str: 格式化后的系统提示词
        """
        prompt_config = self.get_agent_prompt_config(agent_type)
        common_instructions = self.get_common_instructions()
        
        # 组合系统提示词
        full_prompt = prompt_config.system_prompt
        
        # 添加通用指令
        if common_instructions['global_instructions']:
            full_prompt += "\n\n" + common_instructions['global_instructions']
        
        # 格式化提示词
        try:
            formatted_prompt = full_prompt.format(**kwargs)
        except KeyError as e:
            logger.warning(f"⚠️ 提示词格式化缺少参数: {e}")
            formatted_prompt = full_prompt
        
        return formatted_prompt
    
    def format_user_prompt(self, agent_type: str, **kwargs) -> str:
        """
        格式化用户提示词
        
        Args:
            agent_type: 智能体类型
            **kwargs: 格式化参数
            
        Returns:
            str: 格式化后的用户提示词
        """
        prompt_config = self.get_agent_prompt_config(agent_type)
        
        try:
            formatted_prompt = prompt_config.user_prompt_template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"⚠️ 用户提示词格式化缺少参数: {e}")
            formatted_prompt = prompt_config.user_prompt_template
        
        return formatted_prompt
    
    def get_performance_config(self) -> Dict[str, Any]:
        """
        获取性能配置
        
        Returns:
            Dict[str, Any]: 性能配置字典
        """
        return self.llm_config.get('performance', {
            'concurrent_requests': 10,
            'rate_limit_per_minute': 60,
            'cache_enabled': True,
            'cache_ttl': 300
        })
    
    def get_security_config(self) -> Dict[str, Any]:
        """
        获取安全配置
        
        Returns:
            Dict[str, Any]: 安全配置字典
        """
        return self.llm_config.get('security', {
            'content_filter': True,
            'pii_detection': True,
            'safety_settings': {}
        })
    
    def validate_config(self) -> bool:
        """
        验证配置的完整性
        
        Returns:
            bool: 配置是否有效
        """
        try:
            # 验证主要配置
            primary_config = self.get_llm_config()
            if not primary_config.api_key and primary_config.api_key_env:
                if not os.getenv(primary_config.api_key_env):
                    logger.error(f"❌ API密钥环境变量未设置: {primary_config.api_key_env}")
                    return False
            
            # 验证智能体提示词配置
            required_agent_types = ['simulation_scheduler', 'satellite_agents', 'leader_agents']
            for agent_type in required_agent_types:
                prompt_config = self.get_agent_prompt_config(agent_type)
                if not prompt_config.system_prompt:
                    logger.error(f"❌ 智能体类型 {agent_type} 缺少系统提示词")
                    return False
            
            logger.info("✅ 配置验证通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 配置验证失败: {e}")
            return False

    def create_litellm_client(self, agent_type: Optional[str] = None):
        """
        创建LiteLLM客户端

        Args:
            agent_type: 智能体类型，用于获取特定配置

        Returns:
            LiteLLM客户端实例
        """
        try:
            from .litellm_client import create_litellm_client

            # 获取配置
            if agent_type:
                config = self.get_llm_config(agent_type)
            else:
                config = self.get_llm_config()

            # 转换为字典格式
            config_dict = {
                'provider': config.provider,
                'model': config.model,
                'api_key': config.api_key,
                'api_key_env': config.api_key_env,
                'base_url': config.base_url,
                'api_version': config.api_version,
                'max_tokens': config.max_tokens,
                'temperature': config.temperature,
                'top_p': config.top_p,
                'frequency_penalty': config.frequency_penalty,
                'presence_penalty': config.presence_penalty,
                'timeout': config.timeout,
                'retry_attempts': config.retry_attempts,
                'retry_delay': config.retry_delay
            }

            logger.info(f"✅ 创建LiteLLM客户端: {config.model}")
            return create_litellm_client(config_dict)

        except Exception as e:
            logger.error(f"❌ 创建LiteLLM客户端失败: {e}")
            raise


# 全局配置管理器实例
_llm_config_manager = None


def get_llm_config_manager(config_path: str = "config/config.yaml") -> LLMConfigManager:
    """
    获取全局大模型配置管理器实例
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        LLMConfigManager: 配置管理器实例
    """
    global _llm_config_manager
    if _llm_config_manager is None:
        _llm_config_manager = LLMConfigManager(config_path)
    return _llm_config_manager
