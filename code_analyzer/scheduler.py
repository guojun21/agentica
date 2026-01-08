# -*- coding: utf-8 -*-
"""
定时任务调度器 - 定期运行代码分析
"""
import os
import sys
import time
import signal
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable
import json

from code_analyzer.config import AnalyzerConfig
from code_analyzer.analyzer import CodeAnalyzerAgent


class AnalyzerScheduler:
    """分析器调度器"""
    
    def __init__(
        self,
        code_dir: str,
        output_dir: str,
        interval_seconds: int = 3600,
        batch_size: int = 1,
        poe_api_key: Optional[str] = None,
        poe_model: str = "Claude-sonnet",
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        """
        初始化调度器
        
        Args:
            code_dir: 要分析的代码目录
            output_dir: 文档输出目录
            interval_seconds: 运行间隔（秒）
            batch_size: 每次分析的接口数量
            poe_api_key: Poe API 密钥
            poe_model: 使用的模型
            on_complete: 完成回调
            on_error: 错误回调
        """
        self.config = AnalyzerConfig(
            code_dir=code_dir,
            output_dir=output_dir,
            schedule_interval=interval_seconds,
            batch_size=batch_size,
        )
        
        if poe_api_key:
            self.config.poe_api_key = poe_api_key
        if poe_model:
            self.config.poe_model = poe_model
        
        self.on_complete = on_complete
        self.on_error = on_error
        
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._analyzer: Optional[CodeAnalyzerAgent] = None
        
        # 统计信息
        self.stats = {
            "total_runs": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "last_run": None,
            "next_run": None,
            "started_at": None,
        }
    
    def _create_analyzer(self) -> CodeAnalyzerAgent:
        """创建分析器实例"""
        return CodeAnalyzerAgent(self.config)
    
    def _run_once(self) -> dict:
        """执行一次分析"""
        self.stats["total_runs"] += 1
        self.stats["last_run"] = datetime.now().isoformat()
        
        try:
            # 初始化分析器（每次重新创建以获取最新文件）
            self._analyzer = self._create_analyzer()
            self._analyzer.initialize()
            
            # 运行分析
            result = self._analyzer.run_batch()
            
            # 更新统计
            if result.get("results"):
                for r in result["results"]:
                    if r["success"]:
                        self.stats["successful_analyses"] += 1
                    else:
                        self.stats["failed_analyses"] += 1
            
            # 回调
            if self.on_complete:
                self.on_complete(result)
            
            return result
            
        except Exception as e:
            error_info = {
                "error": str(e),
                "time": datetime.now().isoformat()
            }
            
            if self.on_error:
                self.on_error(error_info)
            
            return {"status": "error", "error": str(e)}
    
    def _scheduler_loop(self):
        """调度器主循环"""
        print(f"🚀 调度器启动")
        print(f"   代码目录: {self.config.code_dir}")
        print(f"   输出目录: {self.config.output_dir}")
        print(f"   运行间隔: {self.config.schedule_interval} 秒")
        print(f"   每批数量: {self.config.batch_size}")
        
        self.stats["started_at"] = datetime.now().isoformat()
        
        while not self._stop_event.is_set():
            # 计算下次运行时间
            next_run = datetime.now() + timedelta(seconds=self.config.schedule_interval)
            self.stats["next_run"] = next_run.isoformat()
            
            # 执行分析
            print(f"\n⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行分析任务...")
            result = self._run_once()
            
            # 检查是否全部完成
            if result.get("status") == "completed":
                print("🎉 所有接口分析完成!")
                # 可以选择停止或继续监控新接口
                # self.stop()
                # break
            
            # 打印结果摘要
            if "summary" in result:
                s = result["summary"]
                print(f"📊 当前进度: {s['completed']}/{s['total_endpoints']} ({s['progress_percent']}%)")
            
            # 等待下次执行
            print(f"💤 下次执行: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 使用 Event.wait 以便能够及时响应停止信号
            self._stop_event.wait(self.config.schedule_interval)
        
        print("🛑 调度器已停止")
    
    def start(self, daemon: bool = True):
        """启动调度器"""
        if self._running:
            print("⚠️ 调度器已在运行")
            return
        
        self._running = True
        self._stop_event.clear()
        
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=daemon)
        self._thread.start()
    
    def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        print("\n🛑 正在停止调度器...")
        self._stop_event.set()
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
    
    def run_now(self) -> dict:
        """立即执行一次分析（不等待调度）"""
        return self._run_once()
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        analyzer_status = {}
        if self._analyzer:
            analyzer_status = self._analyzer.get_status()
        
        return {
            "running": self._running,
            "stats": self.stats,
            "config": {
                "code_dir": self.config.code_dir,
                "output_dir": self.config.output_dir,
                "interval_seconds": self.config.schedule_interval,
                "batch_size": self.config.batch_size,
            },
            "analyzer": analyzer_status
        }
    
    def wait(self):
        """等待调度器停止"""
        if self._thread:
            self._thread.join()


def run_scheduler_cli():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="代码接口分析器 - 定时任务调度器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  python scheduler.py --code-dir /path/to/project --output-dir /path/to/docs
  
  # 自定义间隔和批量大小
  python scheduler.py --code-dir /path/to/project --output-dir /path/to/docs \\
      --interval 1800 --batch-size 3
  
  # 立即运行一次（不启动定时任务）
  python scheduler.py --code-dir /path/to/project --output-dir /path/to/docs --once
"""
    )
    
    parser.add_argument(
        "--code-dir", 
        required=True, 
        help="要分析的代码目录（只读）"
    )
    parser.add_argument(
        "--output-dir", 
        required=True, 
        help="文档输出目录"
    )
    parser.add_argument(
        "--interval", 
        type=int, 
        default=3600,
        help="运行间隔（秒），默认 3600（1小时）"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=1,
        help="每次分析的接口数量，默认 1"
    )
    parser.add_argument(
        "--api-key",
        default="W4HQGO1TRCOcZzRv-8vB84REwnexAshVRVVhyZ9dpII",
        help="Poe API 密钥"
    )
    parser.add_argument(
        "--model",
        default="Claude-sonnet",
        help="使用的模型，默认 Claude-sonnet"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只运行一次，不启动定时任务"
    )
    
    args = parser.parse_args()
    
    # 创建调度器
    scheduler = AnalyzerScheduler(
        code_dir=args.code_dir,
        output_dir=args.output_dir,
        interval_seconds=args.interval,
        batch_size=args.batch_size,
        poe_api_key=args.api_key,
        poe_model=args.model,
    )
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print("\n收到停止信号...")
        scheduler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.once:
        # 只运行一次
        result = scheduler.run_now()
        print(f"\n📊 结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        # 启动定时任务
        scheduler.start(daemon=False)
        scheduler.wait()


if __name__ == "__main__":
    run_scheduler_cli()

