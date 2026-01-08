# -*- coding: utf-8 -*-
"""
进度管理器 - 追踪分析进度
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path

from code_analyzer.config import AnalyzerConfig
from code_analyzer.code_reader import EndpointInfo


@dataclass
class EndpointProgress:
    """单个接口的分析进度"""
    endpoint_id: str
    endpoint_name: str
    endpoint_type: str
    file_path: str
    status: str = "pending"  # pending, in_progress, completed, failed
    doc_file: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EndpointProgress':
        return cls(**data)


@dataclass
class AnalysisProgress:
    """整体分析进度"""
    project_name: str
    code_dir: str
    output_dir: str
    total_endpoints: int = 0
    completed_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    last_run: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    endpoints: Dict[str, EndpointProgress] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "project_name": self.project_name,
            "code_dir": self.code_dir,
            "output_dir": self.output_dir,
            "total_endpoints": self.total_endpoints,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "pending_count": self.pending_count,
            "last_run": self.last_run,
            "created_at": self.created_at,
            "endpoints": {k: v.to_dict() for k, v in self.endpoints.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AnalysisProgress':
        endpoints = {k: EndpointProgress.from_dict(v) for k, v in data.get("endpoints", {}).items()}
        return cls(
            project_name=data["project_name"],
            code_dir=data["code_dir"],
            output_dir=data["output_dir"],
            total_endpoints=data.get("total_endpoints", 0),
            completed_count=data.get("completed_count", 0),
            failed_count=data.get("failed_count", 0),
            pending_count=data.get("pending_count", 0),
            last_run=data.get("last_run"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            endpoints=endpoints
        )
    
    def update_counts(self):
        """更新统计计数"""
        self.completed_count = sum(1 for ep in self.endpoints.values() if ep.status == "completed")
        self.failed_count = sum(1 for ep in self.endpoints.values() if ep.status == "failed")
        self.pending_count = sum(1 for ep in self.endpoints.values() if ep.status == "pending")
        self.total_endpoints = len(self.endpoints)


class ProgressManager:
    """进度管理器"""
    
    def __init__(self, config: AnalyzerConfig):
        self.config = config
        self._progress: Optional[AnalysisProgress] = None
    
    def load_progress(self) -> AnalysisProgress:
        """加载进度"""
        if self._progress:
            return self._progress
        
        progress_file = self.config.progress_file_path
        
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._progress = AnalysisProgress.from_dict(data)
            except Exception as e:
                print(f"Error loading progress: {e}")
                self._progress = self._create_new_progress()
        else:
            self._progress = self._create_new_progress()
        
        return self._progress
    
    def _create_new_progress(self) -> AnalysisProgress:
        """创建新的进度记录"""
        project_name = os.path.basename(self.config.code_dir)
        return AnalysisProgress(
            project_name=project_name,
            code_dir=self.config.code_dir,
            output_dir=self.config.output_dir
        )
    
    def save_progress(self):
        """保存进度"""
        if not self._progress:
            return
        
        self._progress.update_counts()
        
        progress_file = self.config.progress_file_path
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(self._progress.to_dict(), f, indent=2, ensure_ascii=False)
    
    def sync_endpoints(self, endpoints: List[EndpointInfo]):
        """同步接口列表（添加新发现的接口，保留已有进度）"""
        progress = self.load_progress()
        
        # 获取当前所有接口ID
        current_ids = {ep.unique_id for ep in endpoints}
        
        # 添加新接口
        for ep in endpoints:
            ep_id = ep.unique_id
            if ep_id not in progress.endpoints:
                progress.endpoints[ep_id] = EndpointProgress(
                    endpoint_id=ep_id,
                    endpoint_name=ep.name,
                    endpoint_type=ep.type,
                    file_path=ep.file_path,
                    status="pending"
                )
        
        # 标记已删除的接口（但保留记录）
        for ep_id in list(progress.endpoints.keys()):
            if ep_id not in current_ids:
                # 可以选择删除或标记为已移除
                pass
        
        progress.update_counts()
        self.save_progress()
    
    def get_next_endpoints(self, batch_size: int = 1) -> List[EndpointProgress]:
        """获取下一批待分析的接口"""
        progress = self.load_progress()
        
        pending = [
            ep for ep in progress.endpoints.values()
            if ep.status == "pending"
        ]
        
        # 按文件路径排序，保持分析顺序
        pending.sort(key=lambda x: (x.file_path, x.endpoint_name))
        
        return pending[:batch_size]
    
    def mark_in_progress(self, endpoint_id: str):
        """标记接口为分析中"""
        progress = self.load_progress()
        
        if endpoint_id in progress.endpoints:
            ep = progress.endpoints[endpoint_id]
            ep.status = "in_progress"
            ep.started_at = datetime.now().isoformat()
            progress.last_run = datetime.now().isoformat()
            self.save_progress()
    
    def mark_completed(self, endpoint_id: str, doc_file: str):
        """标记接口分析完成"""
        progress = self.load_progress()
        
        if endpoint_id in progress.endpoints:
            ep = progress.endpoints[endpoint_id]
            ep.status = "completed"
            ep.doc_file = doc_file
            ep.completed_at = datetime.now().isoformat()
            progress.update_counts()
            self.save_progress()
    
    def mark_failed(self, endpoint_id: str, error_message: str):
        """标记接口分析失败"""
        progress = self.load_progress()
        
        if endpoint_id in progress.endpoints:
            ep = progress.endpoints[endpoint_id]
            ep.status = "failed"
            ep.error_message = error_message
            ep.retry_count += 1
            progress.update_counts()
            self.save_progress()
    
    def reset_failed(self):
        """重置所有失败的接口为待处理"""
        progress = self.load_progress()
        
        for ep in progress.endpoints.values():
            if ep.status == "failed":
                ep.status = "pending"
                ep.error_message = None
        
        progress.update_counts()
        self.save_progress()
    
    def get_completed_docs(self) -> List[str]:
        """获取已完成的文档列表"""
        progress = self.load_progress()
        
        return [
            ep.doc_file for ep in progress.endpoints.values()
            if ep.status == "completed" and ep.doc_file
        ]
    
    def get_summary(self) -> Dict:
        """获取进度摘要"""
        progress = self.load_progress()
        progress.update_counts()
        
        return {
            "project_name": progress.project_name,
            "total_endpoints": progress.total_endpoints,
            "completed": progress.completed_count,
            "pending": progress.pending_count,
            "failed": progress.failed_count,
            "progress_percent": round(progress.completed_count / max(progress.total_endpoints, 1) * 100, 1),
            "last_run": progress.last_run
        }
    
    def scan_existing_docs(self) -> Set[str]:
        """扫描输出目录中已有的文档"""
        existing_docs = set()
        
        doc_dir = Path(self.config.output_dir)
        if doc_dir.exists():
            for doc_file in doc_dir.glob("*.md"):
                existing_docs.add(doc_file.stem)
        
        return existing_docs


if __name__ == "__main__":
    # 测试代码
    config = AnalyzerConfig(
        code_dir=".",
        output_dir="./output"
    )
    manager = ProgressManager(config)
    
    # 测试同步
    from code_analyzer.code_reader import CodeReader
    reader = CodeReader(config)
    endpoints = reader.find_endpoints()
    
    manager.sync_endpoints(endpoints)
    
    print("Summary:", manager.get_summary())
    
    # 获取下一批
    next_batch = manager.get_next_endpoints(3)
    for ep in next_batch:
        print(f"Next: {ep.endpoint_name} ({ep.endpoint_type})")

