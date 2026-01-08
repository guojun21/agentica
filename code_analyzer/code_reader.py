# -*- coding: utf-8 -*-
"""
代码读取工具 - 只读方式读取代码项目
"""
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

from code_analyzer.config import AnalyzerConfig


@dataclass
class EndpointInfo:
    """接口信息"""
    name: str                          # 接口名称
    type: str                          # 类型: http/grpc
    method: Optional[str] = None       # HTTP方法: GET/POST/PUT/DELETE等
    path: Optional[str] = None         # HTTP路径或gRPC服务方法
    file_path: str = ""                # 所在文件
    line_number: int = 0               # 行号
    function_name: str = ""            # 函数/方法名
    service_name: Optional[str] = None # gRPC服务名
    description: Optional[str] = None  # 简短描述
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @property
    def unique_id(self) -> str:
        """生成唯一标识"""
        if self.type == "grpc":
            return f"grpc_{self.service_name}_{self.name}"
        else:
            return f"http_{self.method}_{self.path}".replace("/", "_").replace("{", "").replace("}", "")


@dataclass  
class CodeFile:
    """代码文件信息"""
    path: str
    relative_path: str
    content: str
    language: str
    size: int
    
    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "relative_path": self.relative_path,
            "language": self.language,
            "size": self.size,
            "content_preview": self.content[:500] + "..." if len(self.content) > 500 else self.content
        }


class CodeReader:
    """代码读取器 - 只读操作"""
    
    # 语言检测映射
    LANG_MAP = {
        ".py": "python",
        ".go": "go",
        ".java": "java",
        ".js": "javascript",
        ".ts": "typescript",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".proto": "protobuf",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
    }
    
    # HTTP 接口检测模式
    HTTP_PATTERNS = {
        "python": [
            # Flask
            (r'@app\.route\([\'"]([^\'"]+)[\'"](?:.*methods=\[([^\]]+)\])?', "flask"),
            (r'@bp\.route\([\'"]([^\'"]+)[\'"](?:.*methods=\[([^\]]+)\])?', "flask_bp"),
            # FastAPI
            (r'@(?:app|router)\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]', "fastapi"),
            # Django
            (r'path\([\'"]([^\'"]+)[\'"]', "django"),
        ],
        "go": [
            # Gin - 支持各种变量名如 r, router, g, group, api, v1 等
            (r'(\w+)\.(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\(\s*[\'"]([^\'"]+)[\'"]', "gin"),
            # Echo
            (r'(\w+)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*[\'"]([^\'"]+)[\'"]', "echo"),
            # Chi
            (r'(\w+)\.(Get|Post|Put|Delete|Patch)\s*\(\s*[\'"]([^\'"]+)[\'"]', "chi"),
            # net/http
            (r'http\.HandleFunc\s*\(\s*[\'"]([^\'"]+)[\'"]', "net_http"),
            # Fiber
            (r'(\w+)\.(Get|Post|Put|Delete|Patch)\s*\(\s*[\'"]([^\'"]+)[\'"]', "fiber"),
        ],
        "java": [
            # Spring
            (r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\([\'"]?([^\'")\s]+)?', "spring"),
            (r'@RequestMapping\((?:value\s*=\s*)?[\'"]([^\'"]+)[\'"](?:.*method\s*=\s*RequestMethod\.(\w+))?', "spring_rm"),
        ],
        "javascript": [
            # Express
            (r'(?:app|router)\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]', "express"),
        ],
        "typescript": [
            # Express/NestJS
            (r'(?:app|router)\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]', "express"),
            (r'@(Get|Post|Put|Delete|Patch)\([\'"]?([^\'")\s]+)?', "nestjs"),
        ],
    }
    
    # gRPC 接口检测模式
    GRPC_PATTERNS = {
        "protobuf": [
            (r'service\s+(\w+)\s*\{', "service"),
            (r'rpc\s+(\w+)\s*\(', "rpc"),
        ],
        "go": [
            # gRPC server implementation
            (r'func\s*\([^)]+\)\s*(\w+)\s*\([^)]*pb\.\w+', "grpc_impl"),
            (r'Register(\w+)Server\s*\(', "grpc_register"),
        ],
        "python": [
            (r'class\s+(\w+)Servicer\s*\(', "grpc_servicer"),
            (r'def\s+(\w+)\s*\(self,\s*request', "grpc_method"),
        ],
        "java": [
            (r'class\s+(\w+)\s+extends\s+\w+Grpc\.\w+ImplBase', "grpc_impl"),
            (r'public\s+\w+\s+(\w+)\s*\([^)]*\w+Request', "grpc_method"),
        ],
    }
    
    def __init__(self, config: AnalyzerConfig):
        self.config = config
        self._file_cache: Dict[str, CodeFile] = {}
    
    def scan_project(self) -> Dict:
        """扫描项目结构"""
        project_info = {
            "root": self.config.code_dir,
            "files": [],
            "directories": [],
            "stats": {
                "total_files": 0,
                "total_lines": 0,
                "by_language": {}
            }
        }
        
        for root, dirs, files in os.walk(self.config.code_dir):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if not self.config.should_ignore_dir(d)]
            
            rel_root = os.path.relpath(root, self.config.code_dir)
            if rel_root != ".":
                project_info["directories"].append(rel_root)
            
            for file in files:
                file_path = os.path.join(root, file)
                if self.config.is_valid_code_file(file_path):
                    rel_path = os.path.relpath(file_path, self.config.code_dir)
                    project_info["files"].append(rel_path)
                    project_info["stats"]["total_files"] += 1
                    
                    # 统计语言
                    ext = os.path.splitext(file)[1]
                    lang = self.LANG_MAP.get(ext, "unknown")
                    project_info["stats"]["by_language"][lang] = \
                        project_info["stats"]["by_language"].get(lang, 0) + 1
        
        return project_info
    
    def read_file(self, file_path: str) -> Optional[CodeFile]:
        """读取单个代码文件"""
        # 检查缓存
        if file_path in self._file_cache:
            return self._file_cache[file_path]
        
        # 构建完整路径
        if not os.path.isabs(file_path):
            full_path = os.path.join(self.config.code_dir, file_path)
        else:
            full_path = file_path
        
        # 安全检查：确保在代码目录内
        if not os.path.abspath(full_path).startswith(os.path.abspath(self.config.code_dir)):
            raise PermissionError(f"Access denied: {file_path} is outside code directory")
        
        if not os.path.exists(full_path):
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            ext = os.path.splitext(full_path)[1]
            code_file = CodeFile(
                path=full_path,
                relative_path=os.path.relpath(full_path, self.config.code_dir),
                content=content,
                language=self.LANG_MAP.get(ext, "unknown"),
                size=len(content)
            )
            
            self._file_cache[file_path] = code_file
            return code_file
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None
    
    def find_endpoints(self) -> List[EndpointInfo]:
        """查找所有接口（HTTP和gRPC）"""
        endpoints = []
        seen_ids = set()  # 用于去重
        
        for root, dirs, files in os.walk(self.config.code_dir):
            dirs[:] = [d for d in dirs if not self.config.should_ignore_dir(d)]
            
            for file in files:
                file_path = os.path.join(root, file)
                if not self.config.is_valid_code_file(file_path):
                    continue
                
                code_file = self.read_file(file_path)
                if not code_file:
                    continue
                
                # 查找HTTP接口
                http_endpoints = self._find_http_endpoints(code_file)
                for ep in http_endpoints:
                    if ep.unique_id not in seen_ids:
                        seen_ids.add(ep.unique_id)
                        endpoints.append(ep)
                
                # 查找gRPC接口
                grpc_endpoints = self._find_grpc_endpoints(code_file)
                for ep in grpc_endpoints:
                    if ep.unique_id not in seen_ids:
                        seen_ids.add(ep.unique_id)
                        endpoints.append(ep)
        
        return endpoints
    
    def _find_http_endpoints(self, code_file: CodeFile) -> List[EndpointInfo]:
        """查找HTTP接口"""
        endpoints = []
        patterns = self.HTTP_PATTERNS.get(code_file.language, [])
        
        lines = code_file.content.split('\n')
        
        for pattern, framework in patterns:
            for match in re.finditer(pattern, code_file.content, re.MULTILINE):
                # 计算行号
                line_num = code_file.content[:match.start()].count('\n') + 1
                
                # 解析匹配结果
                groups = match.groups()
                
                if framework in ["gin", "echo", "chi", "fiber"]:
                    # Go 框架: (变量名, 方法, 路径)
                    method = groups[1].upper() if len(groups) > 1 else "GET"
                    path = groups[2] if len(groups) > 2 and groups[2] else "/"
                elif framework in ["fastapi", "express", "nestjs"]:
                    method = groups[0].upper()
                    path = groups[1] if len(groups) > 1 and groups[1] else "/"
                elif framework in ["flask", "flask_bp"]:
                    path = groups[0]
                    method = "GET"  # 默认
                    if len(groups) > 1 and groups[1]:
                        methods = re.findall(r"'(\w+)'", groups[1])
                        method = methods[0].upper() if methods else "GET"
                elif framework == "spring":
                    mapping_type = groups[0]
                    path = groups[1] if groups[1] else "/"
                    method = mapping_type.replace("Mapping", "").upper()
                elif framework == "spring_rm":
                    path = groups[0]
                    method = groups[1] if len(groups) > 1 and groups[1] else "GET"
                else:
                    path = groups[0] if groups else "/"
                    method = "GET"
                
                # 查找关联的函数名
                func_name = self._find_function_at_line(lines, line_num, code_file.language)
                
                endpoint = EndpointInfo(
                    name=func_name or f"{method}_{path}",
                    type="http",
                    method=method,
                    path=path,
                    file_path=code_file.relative_path,
                    line_number=line_num,
                    function_name=func_name or ""
                )
                endpoints.append(endpoint)
        
        return endpoints
    
    def _find_grpc_endpoints(self, code_file: CodeFile) -> List[EndpointInfo]:
        """查找gRPC接口"""
        endpoints = []
        patterns = self.GRPC_PATTERNS.get(code_file.language, [])
        
        current_service = None
        lines = code_file.content.split('\n')
        
        for pattern, pattern_type in patterns:
            for match in re.finditer(pattern, code_file.content, re.MULTILINE):
                line_num = code_file.content[:match.start()].count('\n') + 1
                name = match.group(1)
                
                if pattern_type == "service":
                    current_service = name
                elif pattern_type in ["rpc", "grpc_method", "grpc_impl"]:
                    endpoint = EndpointInfo(
                        name=name,
                        type="grpc",
                        service_name=current_service,
                        file_path=code_file.relative_path,
                        line_number=line_num,
                        function_name=name
                    )
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _find_function_at_line(self, lines: List[str], line_num: int, language: str) -> Optional[str]:
        """查找指定行附近的函数名"""
        func_patterns = {
            "python": r'def\s+(\w+)\s*\(',
            "go": r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(',
            "java": r'(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(',
            "javascript": r'(?:function\s+(\w+)|(\w+)\s*[=:]\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))',
            "typescript": r'(?:function\s+(\w+)|(\w+)\s*[=:]\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))',
        }
        
        pattern = func_patterns.get(language)
        if not pattern:
            return None
        
        # 向下搜索几行找函数定义
        for i in range(line_num - 1, min(line_num + 5, len(lines))):
            if i < 0:
                continue
            match = re.search(pattern, lines[i])
            if match:
                # 返回第一个非空的捕获组
                for g in match.groups():
                    if g:
                        return g
        
        return None
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """获取文件内容（只读）"""
        code_file = self.read_file(file_path)
        return code_file.content if code_file else None
    
    def search_in_files(self, query: str, file_extensions: Optional[List[str]] = None) -> List[Dict]:
        """在文件中搜索内容"""
        results = []
        
        for root, dirs, files in os.walk(self.config.code_dir):
            dirs[:] = [d for d in dirs if not self.config.should_ignore_dir(d)]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # 检查扩展名
                if file_extensions:
                    ext = os.path.splitext(file)[1]
                    if ext not in file_extensions:
                        continue
                elif not self.config.is_valid_code_file(file_path):
                    continue
                
                code_file = self.read_file(file_path)
                if not code_file:
                    continue
                
                # 搜索内容
                lines = code_file.content.split('\n')
                for i, line in enumerate(lines):
                    if query.lower() in line.lower():
                        results.append({
                            "file": code_file.relative_path,
                            "line_number": i + 1,
                            "line_content": line.strip(),
                            "context": self._get_context(lines, i, 2)
                        })
        
        return results
    
    def _get_context(self, lines: List[str], line_idx: int, context_size: int = 2) -> str:
        """获取上下文"""
        start = max(0, line_idx - context_size)
        end = min(len(lines), line_idx + context_size + 1)
        
        context_lines = []
        for i in range(start, end):
            prefix = ">>> " if i == line_idx else "    "
            context_lines.append(f"{prefix}{i + 1}: {lines[i]}")
        
        return "\n".join(context_lines)
    
    def get_call_graph(self, function_name: str, file_path: str) -> Dict:
        """获取函数调用图（简化版）"""
        code_file = self.read_file(file_path)
        if not code_file:
            return {"error": f"File not found: {file_path}"}
        
        # 查找函数调用
        calls = []
        
        # 简单的函数调用检测
        call_pattern = r'(\w+)\s*\('
        for match in re.finditer(call_pattern, code_file.content):
            called_func = match.group(1)
            # 过滤关键字和内置函数
            if called_func not in ['if', 'for', 'while', 'switch', 'return', 'print', 'len', 'range']:
                calls.append(called_func)
        
        return {
            "function": function_name,
            "file": file_path,
            "calls": list(set(calls))
        }


if __name__ == "__main__":
    # 测试代码
    config = AnalyzerConfig(
        code_dir=".",
        output_dir="./output"
    )
    reader = CodeReader(config)
    
    # 扫描项目
    project = reader.scan_project()
    print(f"Found {project['stats']['total_files']} files")
    
    # 查找接口
    endpoints = reader.find_endpoints()
    print(f"Found {len(endpoints)} endpoints")
    for ep in endpoints[:5]:
        print(f"  - {ep.type}: {ep.method} {ep.path} ({ep.file_path}:{ep.line_number})")

