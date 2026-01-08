# -*- coding: utf-8 -*-
"""
代码分析器配置
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class AnalyzerConfig:
    """分析器配置"""
    
    # 要分析的代码目录（只读）
    code_dir: str
    
    # 文档输出目录
    output_dir: str
    
    # Poe API 配置
    poe_api_key: str = "W4HQGO1TRCOcZzRv-8vB84REwnexAshVRVVhyZ9dpII"
    poe_base_url: str = "https://api.poe.com/v1"
    poe_model: str = "Claude-sonnet"  # Claude 4.5 Opus
    
    # 支持的代码文件扩展名
    code_extensions: List[str] = field(default_factory=lambda: [
        ".py", ".go", ".java", ".js", ".ts", ".rs", ".cpp", ".c", ".h",
        ".proto", ".yaml", ".yml", ".json"
    ])
    
    # 忽略的目录
    ignore_dirs: List[str] = field(default_factory=lambda: [
        ".git", ".svn", "node_modules", "__pycache__", ".idea", ".vscode",
        "vendor", "venv", "env", ".env", "dist", "build", "target"
    ])
    
    # 定时任务间隔（秒）
    schedule_interval: int = 3600  # 默认1小时
    
    # 每次分析的接口数量
    batch_size: int = 1
    
    # 进度文件名
    progress_file: str = "analysis_progress.json"
    
    def __post_init__(self):
        """初始化后处理"""
        self.code_dir = os.path.abspath(self.code_dir)
        self.output_dir = os.path.abspath(self.output_dir)
        
        # 确保输出目录存在
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    @property
    def progress_file_path(self) -> str:
        """进度文件完整路径"""
        return os.path.join(self.output_dir, self.progress_file)
    
    def is_valid_code_file(self, file_path: str) -> bool:
        """检查是否是有效的代码文件"""
        return any(file_path.endswith(ext) for ext in self.code_extensions)
    
    def should_ignore_dir(self, dir_name: str) -> bool:
        """检查是否应该忽略的目录"""
        return dir_name in self.ignore_dirs or dir_name.startswith(".")

