# -*- coding: utf-8 -*-
"""
代码分析器 Agent - 使用 Poe Claude 4.5 Opus 分析代码接口
"""
import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# 添加 agentica 到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentica import Agent
from agentica.model.openai import OpenAILike
from agentica.tools.base import Tool

from code_analyzer.config import AnalyzerConfig
from code_analyzer.code_reader import CodeReader, EndpointInfo, CodeFile
from code_analyzer.progress_manager import ProgressManager, EndpointProgress


class CodeAnalysisTool(Tool):
    """代码分析工具 - 提供给 Agent 使用的只读代码访问能力"""
    
    def __init__(self, code_reader: CodeReader):
        super().__init__(name="code_analysis_tool")
        self.reader = code_reader
        
        # 注册工具函数
        self.register(self.read_code_file)
        self.register(self.search_code)
        self.register(self.list_project_files)
        self.register(self.find_function_calls)
        self.register(self.get_file_structure)
    
    def read_code_file(self, file_path: str) -> str:
        """读取代码文件内容
        
        Args:
            file_path: 文件路径（相对于项目根目录）
            
        Returns:
            文件内容，如果文件不存在返回错误信息
        """
        code_file = self.reader.read_file(file_path)
        if code_file:
            return f"文件: {code_file.relative_path}\n语言: {code_file.language}\n\n```{code_file.language}\n{code_file.content}\n```"
        return f"错误: 文件 {file_path} 不存在或无法读取"
    
    def search_code(self, query: str, file_extensions: str = "") -> str:
        """在代码中搜索内容
        
        Args:
            query: 搜索关键词
            file_extensions: 文件扩展名过滤，逗号分隔，如 ".py,.go"
            
        Returns:
            搜索结果列表
        """
        ext_list = [e.strip() for e in file_extensions.split(",")] if file_extensions else None
        results = self.reader.search_in_files(query, ext_list)
        
        if not results:
            return f"未找到包含 '{query}' 的内容"
        
        output = [f"找到 {len(results)} 处匹配:\n"]
        for r in results[:20]:  # 限制结果数量
            output.append(f"\n文件: {r['file']} (行 {r['line_number']})")
            output.append(f"内容: {r['line_content']}")
            output.append(f"上下文:\n{r['context']}")
        
        if len(results) > 20:
            output.append(f"\n... 还有 {len(results) - 20} 处匹配")
        
        return "\n".join(output)
    
    def list_project_files(self, directory: str = "") -> str:
        """列出项目文件
        
        Args:
            directory: 子目录路径，空则列出根目录
            
        Returns:
            文件列表
        """
        project = self.reader.scan_project()
        
        if directory:
            files = [f for f in project["files"] if f.startswith(directory)]
        else:
            files = project["files"]
        
        output = [f"项目文件列表 ({len(files)} 个文件):\n"]
        
        # 按目录分组
        by_dir: Dict[str, List[str]] = {}
        for f in files:
            dir_name = os.path.dirname(f) or "."
            if dir_name not in by_dir:
                by_dir[dir_name] = []
            by_dir[dir_name].append(os.path.basename(f))
        
        for dir_name in sorted(by_dir.keys()):
            output.append(f"\n📁 {dir_name}/")
            for file_name in sorted(by_dir[dir_name])[:20]:
                output.append(f"   📄 {file_name}")
            if len(by_dir[dir_name]) > 20:
                output.append(f"   ... 还有 {len(by_dir[dir_name]) - 20} 个文件")
        
        return "\n".join(output)
    
    def find_function_calls(self, function_name: str, file_path: str) -> str:
        """查找函数调用关系
        
        Args:
            function_name: 函数名
            file_path: 文件路径
            
        Returns:
            调用关系信息
        """
        call_graph = self.reader.get_call_graph(function_name, file_path)
        
        if "error" in call_graph:
            return call_graph["error"]
        
        output = [f"函数 {function_name} 的调用分析:\n"]
        output.append(f"文件: {call_graph['file']}")
        output.append(f"调用的函数: {', '.join(call_graph['calls'][:30])}")
        
        return "\n".join(output)
    
    def get_file_structure(self, file_path: str) -> str:
        """获取文件结构（函数、类定义等）
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件结构信息
        """
        code_file = self.reader.read_file(file_path)
        if not code_file:
            return f"错误: 文件 {file_path} 不存在"
        
        import re
        
        structures = []
        lines = code_file.content.split('\n')
        
        # 根据语言提取结构
        patterns = {
            "python": [
                (r'^class\s+(\w+)', "类"),
                (r'^def\s+(\w+)', "函数"),
                (r'^async\s+def\s+(\w+)', "异步函数"),
            ],
            "go": [
                (r'^type\s+(\w+)\s+struct', "结构体"),
                (r'^type\s+(\w+)\s+interface', "接口"),
                (r'^func\s+(?:\([^)]+\)\s+)?(\w+)', "函数"),
            ],
            "java": [
                (r'class\s+(\w+)', "类"),
                (r'interface\s+(\w+)', "接口"),
                (r'(?:public|private|protected)\s+\w+\s+(\w+)\s*\(', "方法"),
            ],
        }
        
        lang_patterns = patterns.get(code_file.language, [])
        
        for i, line in enumerate(lines):
            for pattern, type_name in lang_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    structures.append({
                        "type": type_name,
                        "name": match.group(1),
                        "line": i + 1
                    })
        
        output = [f"文件结构: {code_file.relative_path}\n"]
        for s in structures:
            output.append(f"  [{s['type']}] {s['name']} (行 {s['line']})")
        
        return "\n".join(output) if structures else "未找到明显的结构定义"


class CodeAnalyzerAgent:
    """代码分析器 Agent"""
    
    # 分析提示词模板
    ANALYSIS_PROMPT = """你是一个专业的代码分析师。你的任务是分析一个接口（API endpoint），从入口到数据库层，完整地理解和记录它的业务逻辑。

## 当前任务

分析接口: {endpoint_name}
类型: {endpoint_type}
{endpoint_details}
文件位置: {file_path}

## 分析要求

请按照以下结构进行分析，生成详细的文档：

### 1. 接口概述
- 接口名称和类型
- 请求方法和路径（HTTP）或服务方法（gRPC）
- 主要功能描述

### 2. 请求参数
- 输入参数列表
- 参数类型和验证规则
- 必填/可选说明

### 3. 处理流程
按顺序分析从接口入口到数据库的完整调用链：

```
入口函数
  ├── 参数验证
  ├── 业务逻辑层调用
  │   ├── 具体业务处理
  │   ├── 条件分支1: xxx
  │   └── 条件分支2: xxx
  └── 数据访问层
      ├── 数据库查询/写入
      └── 缓存操作（如有）
```

对于每一层：
- 函数名和所在文件
- 主要逻辑说明
- 条件分支和判断
- 错误处理方式

### 4. 数据库操作
- 涉及的表
- SQL操作类型（SELECT/INSERT/UPDATE/DELETE）
- 关键查询条件

### 5. 返回结果
- 响应数据结构
- 可能的错误码和含义

### 6. 业务目的总结
用简洁的语言总结这个接口的业务目的和价值。

## 注意事项
- 只能读取代码，不能修改任何文件
- 使用提供的工具来读取文件和搜索代码
- 如果某些信息无法确定，请明确标注"待确认"
- 保持客观，基于代码事实进行分析

请开始分析。"""

    def __init__(self, config: AnalyzerConfig):
        self.config = config
        self.code_reader = CodeReader(config)
        self.progress_manager = ProgressManager(config)
        
        # 创建 Poe Claude 模型
        self.model = OpenAILike(
            id=config.poe_model,
            api_key=config.poe_api_key,
            base_url=config.poe_base_url,
        )
        
        # 创建代码分析工具
        self.code_tool = CodeAnalysisTool(self.code_reader)
        
        # 创建 Agent
        self.agent = Agent(
            name="CodeAnalyzer",
            model=self.model,
            tools=[self.code_tool],
            description="专业的代码分析师，负责分析API接口的完整调用链和业务逻辑",
            instructions=[
                "你是一个代码分析专家，负责分析代码项目中的接口",
                "你只能读取代码，绝对不能修改任何文件",
                "分析时要从接口入口追踪到数据库层",
                "记录所有的条件分支和业务逻辑",
                "使用中文输出分析结果",
            ],
            show_tool_calls=True,
        )
    
    def initialize(self):
        """初始化：扫描项目并同步进度"""
        print(f"🔍 扫描项目: {self.config.code_dir}")
        
        # 查找所有接口
        endpoints = self.code_reader.find_endpoints()
        print(f"📋 发现 {len(endpoints)} 个接口")
        
        # 同步进度
        self.progress_manager.sync_endpoints(endpoints)
        
        # 显示摘要
        summary = self.progress_manager.get_summary()
        print(f"📊 进度: {summary['completed']}/{summary['total_endpoints']} ({summary['progress_percent']}%)")
        
        return endpoints
    
    def analyze_endpoint(self, endpoint: EndpointProgress) -> Optional[str]:
        """分析单个接口"""
        print(f"\n🔬 开始分析: {endpoint.endpoint_name} ({endpoint.endpoint_type})")
        
        # 标记为进行中
        self.progress_manager.mark_in_progress(endpoint.endpoint_id)
        
        try:
            # 读取接口所在文件
            code_file = self.code_reader.read_file(endpoint.file_path)
            if not code_file:
                raise Exception(f"无法读取文件: {endpoint.file_path}")
            
            # 构建分析提示
            endpoint_details = ""
            if endpoint.endpoint_type == "http":
                # 从进度中获取更多信息
                endpoint_details = "HTTP接口"
            else:
                endpoint_details = f"gRPC服务方法"
            
            prompt = self.ANALYSIS_PROMPT.format(
                endpoint_name=endpoint.endpoint_name,
                endpoint_type=endpoint.endpoint_type,
                endpoint_details=endpoint_details,
                file_path=endpoint.file_path,
            )
            
            # 调用 Agent 进行分析
            response = self.agent.run(prompt)
            
            # 提取分析结果
            if hasattr(response, 'content'):
                analysis_result = response.content
            else:
                analysis_result = str(response)
            
            # 保存文档
            doc_file = self._save_document(endpoint, analysis_result)
            
            # 标记完成
            self.progress_manager.mark_completed(endpoint.endpoint_id, doc_file)
            
            print(f"✅ 分析完成: {doc_file}")
            return doc_file
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 分析失败: {error_msg}")
            self.progress_manager.mark_failed(endpoint.endpoint_id, error_msg)
            return None
    
    def _save_document(self, endpoint: EndpointProgress, content: str) -> str:
        """保存分析文档"""
        # 生成文件名
        safe_name = endpoint.endpoint_name.replace("/", "_").replace(":", "_").replace("{", "").replace("}", "")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{endpoint.endpoint_type}_{safe_name}_{timestamp}.md"
        
        # 完整路径
        doc_path = os.path.join(self.config.output_dir, filename)
        
        # 添加元数据头
        header = f"""---
endpoint_id: {endpoint.endpoint_id}
endpoint_name: {endpoint.endpoint_name}
endpoint_type: {endpoint.endpoint_type}
file_path: {endpoint.file_path}
generated_at: {datetime.now().isoformat()}
---

"""
        
        # 写入文件
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(header + content)
        
        return filename
    
    def run_batch(self, batch_size: int = None) -> Dict:
        """运行一批分析"""
        if batch_size is None:
            batch_size = self.config.batch_size
        
        # 获取下一批待分析的接口
        next_batch = self.progress_manager.get_next_endpoints(batch_size)
        
        if not next_batch:
            print("🎉 所有接口已分析完成!")
            return {"status": "completed", "analyzed": 0}
        
        print(f"\n📦 本批次将分析 {len(next_batch)} 个接口")
        
        results = []
        for endpoint in next_batch:
            doc_file = self.analyze_endpoint(endpoint)
            results.append({
                "endpoint": endpoint.endpoint_name,
                "success": doc_file is not None,
                "doc_file": doc_file
            })
        
        summary = self.progress_manager.get_summary()
        
        return {
            "status": "in_progress",
            "analyzed": len(results),
            "results": results,
            "summary": summary
        }
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        return self.progress_manager.get_summary()


def create_analyzer(code_dir: str, output_dir: str, **kwargs) -> CodeAnalyzerAgent:
    """创建分析器实例的便捷函数"""
    config = AnalyzerConfig(
        code_dir=code_dir,
        output_dir=output_dir,
        **kwargs
    )
    return CodeAnalyzerAgent(config)


if __name__ == "__main__":
    # 测试代码
    import argparse
    
    parser = argparse.ArgumentParser(description="代码接口分析器")
    parser.add_argument("--code-dir", required=True, help="要分析的代码目录")
    parser.add_argument("--output-dir", required=True, help="文档输出目录")
    parser.add_argument("--batch-size", type=int, default=1, help="每批分析的接口数量")
    
    args = parser.parse_args()
    
    analyzer = create_analyzer(
        code_dir=args.code_dir,
        output_dir=args.output_dir,
        batch_size=args.batch_size
    )
    
    # 初始化
    analyzer.initialize()
    
    # 运行一批分析
    result = analyzer.run_batch()
    print(f"\n📊 结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

