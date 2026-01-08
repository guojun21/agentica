#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试脚本 - 测试代码读取和接口发现功能
不调用 API，只测试本地功能
"""
import os
import sys
import json

# 确保可以导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_analyzer.config import AnalyzerConfig
from code_analyzer.code_reader import CodeReader
from code_analyzer.progress_manager import ProgressManager


def test_code_reader(code_dir: str, output_dir: str):
    """测试代码读取器"""
    print(f"\n{'='*60}")
    print(f"测试代码读取器")
    print(f"{'='*60}")
    
    config = AnalyzerConfig(
        code_dir=code_dir,
        output_dir=output_dir
    )
    
    reader = CodeReader(config)
    
    # 1. 扫描项目
    print("\n1. 扫描项目结构...")
    project = reader.scan_project()
    print(f"   文件总数: {project['stats']['total_files']}")
    print(f"   语言分布: {project['stats']['by_language']}")
    
    # 2. 查找接口
    print("\n2. 查找接口...")
    endpoints = reader.find_endpoints()
    print(f"   发现 {len(endpoints)} 个接口")
    
    for ep in endpoints:
        print(f"   - [{ep.type}] {ep.name}")
        print(f"     文件: {ep.file_path}:{ep.line_number}")
        if ep.type == "http":
            print(f"     方法: {ep.method} {ep.path}")
        elif ep.type == "grpc":
            print(f"     服务: {ep.service_name}")
    
    # 3. 读取文件
    print("\n3. 测试文件读取...")
    if project['files']:
        test_file = project['files'][0]
        code_file = reader.read_file(test_file)
        if code_file:
            print(f"   读取文件: {code_file.relative_path}")
            print(f"   语言: {code_file.language}")
            print(f"   大小: {code_file.size} 字节")
            print(f"   前100字符: {code_file.content[:100]}...")
    
    # 4. 搜索功能
    print("\n4. 测试搜索功能...")
    results = reader.search_in_files("func", [".go"])
    print(f"   搜索 'func' 在 .go 文件中: 找到 {len(results)} 处")
    for r in results[:3]:
        print(f"   - {r['file']}:{r['line_number']}")
    
    return endpoints


def test_progress_manager(code_dir: str, output_dir: str, endpoints):
    """测试进度管理器"""
    print(f"\n{'='*60}")
    print(f"测试进度管理器")
    print(f"{'='*60}")
    
    config = AnalyzerConfig(
        code_dir=code_dir,
        output_dir=output_dir
    )
    
    manager = ProgressManager(config)
    
    # 1. 同步接口
    print("\n1. 同步接口列表...")
    manager.sync_endpoints(endpoints)
    
    # 2. 获取摘要
    print("\n2. 获取进度摘要...")
    summary = manager.get_summary()
    print(f"   项目: {summary['project_name']}")
    print(f"   总接口: {summary['total_endpoints']}")
    print(f"   待处理: {summary['pending']}")
    print(f"   已完成: {summary['completed']}")
    
    # 3. 获取下一批
    print("\n3. 获取下一批待分析接口...")
    next_batch = manager.get_next_endpoints(2)
    for ep in next_batch:
        print(f"   - {ep.endpoint_name} ({ep.endpoint_type})")
    
    return manager


def test_document_generation(code_dir: str, output_dir: str, endpoints):
    """测试文档生成（模拟，不调用 API）"""
    print(f"\n{'='*60}")
    print(f"测试文档生成（模拟）")
    print(f"{'='*60}")
    
    if not endpoints:
        print("   没有接口可以测试")
        return
    
    # 模拟生成一个文档
    ep = endpoints[0]
    
    mock_doc = f"""---
endpoint_id: {ep.unique_id}
endpoint_name: {ep.name}
endpoint_type: {ep.type}
file_path: {ep.file_path}
generated_at: 2024-01-08T12:00:00
---

# 接口文档: {ep.name}

## 1. 接口概述

这是一个 {ep.type.upper()} 接口，位于 `{ep.file_path}` 文件的第 {ep.line_number} 行。

## 2. 请求参数

（待 AI 分析填充）

## 3. 处理流程

```
{ep.function_name or ep.name}
  ├── 参数验证
  ├── 业务逻辑处理
  └── 返回结果
```

## 4. 数据库操作

（待 AI 分析填充）

## 5. 返回结果

（待 AI 分析填充）

## 6. 业务目的

（待 AI 分析填充）
"""
    
    # 保存文档
    doc_path = os.path.join(output_dir, f"test_{ep.unique_id}.md")
    with open(doc_path, 'w', encoding='utf-8') as f:
        f.write(mock_doc)
    
    print(f"   生成测试文档: {doc_path}")
    print(f"   文档内容预览:")
    print("-" * 40)
    print(mock_doc[:500])
    print("-" * 40)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="代码分析器简单测试")
    parser.add_argument("--code-dir", required=True, help="代码目录")
    parser.add_argument("--output-dir", default="/tmp/code_analyzer_test", help="输出目录")
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"代码目录: {args.code_dir}")
    print(f"输出目录: {args.output_dir}")
    
    # 运行测试
    endpoints = test_code_reader(args.code_dir, args.output_dir)
    manager = test_progress_manager(args.code_dir, args.output_dir, endpoints)
    test_document_generation(args.code_dir, args.output_dir, endpoints)
    
    print(f"\n{'='*60}")
    print("✅ 所有测试完成!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

