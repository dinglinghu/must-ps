"""
简单的会话脚本，用于启动多智能体系统
解决ADK会话管理问题
"""

import logging
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/simple_session.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# ADK框架导入
from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions import Session, InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

# 导入多智能体系统
from src.agents.multi_agent_system import MultiAgentSystem


async def create_and_run_session():
    """创建会话并运行多智能体系统"""
    try:
        logger.info("🚀 启动简单会话脚本")
        
        # 创建输出目录
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # 初始化多智能体系统
        logger.info("🔧 初始化多智能体系统...")
        multi_agent_system = MultiAgentSystem(
            config_path="config/config.yaml",
            output_dir=str(output_dir)
        )
        
        # 创建会话服务
        logger.info("📝 创建会话服务...")
        session_service = InMemorySessionService()
        
        # 创建会话
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"🆔 创建会话: {session_id}")
        
        # 手动创建会话对象并添加到服务中
        session = Session(
            id=session_id,
            appName="MultiAgentPlanningSystem",
            user_id="system"
        )
        
        # 直接将会话添加到内存服务中
        session_service._sessions[session_id] = session
        logger.info(f"✅ 会话已添加到服务: {session_id}")
        
        # 创建Runner
        logger.info("🏃 创建ADK Runner...")
        runner = Runner(
            app_name="MultiAgentPlanningSystem",
            agent=multi_agent_system,
            session_service=session_service
        )
        
        # 创建初始消息
        initial_message = types.Content(parts=[
            types.Part(text="开始多智能体协同任务规划仿真")
        ])
        
        # 运行仿真
        logger.info("▶️ 开始仿真运行...")
        start_time = datetime.now()
        
        event_count = 0
        max_events = 10  # 限制事件数量以避免长时间运行
        
        async for event in runner.run_async(
            user_id="system",
            session_id=session_id,
            new_message=initial_message
        ):
            event_count += 1
            
            # 输出事件信息
            if event.content and event.content.parts:
                content_text = event.content.parts[0].text
                logger.info(f"[{event.author}] {content_text}")
                print(f"[{event.author}] {content_text}")
            
            # 检查是否为最终事件或达到最大事件数
            if event.is_final_response() or event_count >= max_events:
                logger.info("🏁 仿真完成")
                break
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 输出仿真统计
        logger.info(f"📊 仿真统计:")
        logger.info(f"   - 开始时间: {start_time}")
        logger.info(f"   - 结束时间: {end_time}")
        logger.info(f"   - 运行时长: {duration:.2f} 秒")
        logger.info(f"   - 事件数量: {event_count}")
        
        # 获取系统状态
        system_status = multi_agent_system.get_system_status()
        logger.info(f"   - 卫星智能体: {system_status['satellite_agents_count']}")
        logger.info(f"   - 组长智能体: {system_status['leader_agents_count']}")
        logger.info(f"   - 活跃讨论组: {system_status['active_groups_count']}")
        logger.info(f"   - 输出目录: {system_status['output_directory']}")
        
        print("\n" + "="*60)
        print("🎉 多智能体协同任务规划仿真完成!")
        print(f"📁 输出目录: {system_status['output_directory']}")
        print(f"⏱️ 运行时长: {duration:.2f} 秒")
        print(f"📊 处理事件: {event_count}")
        print("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 仿真运行失败: {e}")
        print(f"\n❌ 仿真运行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        print("🚀 简单会话脚本 - 多智能体系统启动器")
        print("=" * 60)
        print("功能:")
        print("- 自动创建和管理ADK会话")
        print("- 启动基于真实ADK框架的多智能体系统")
        print("- 运行多星多任务规划仿真")
        print("- 输出详细的运行日志和统计信息")
        print("=" * 60)
        
        # 检查配置文件
        config_file = Path("config/config.yaml")
        if not config_file.exists():
            print("❌ 配置文件不存在: config/config.yaml")
            return False
        
        # 运行仿真
        success = asyncio.run(create_and_run_session())
        
        if success:
            print("\n✅ 系统运行成功完成")
            return True
        else:
            print("\n❌ 系统运行失败")
            return False
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断仿真")
        logger.info("用户中断仿真")
        return False
    except Exception as e:
        print(f"\n💥 系统异常: {e}")
        logger.error(f"系统异常: {e}")
        return False


if __name__ == "__main__":
    # 设置事件循环策略（Windows兼容性）
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    success = main()
    sys.exit(0 if success else 1)
