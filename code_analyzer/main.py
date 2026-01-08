#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代码接口分析器 - 主入口
自动分析代码项目中的接口(gRPC/HTTP)，生成详细文档

使用方法:
    # 立即分析一次
    python main.py analyze --code-dir /path/to/project --output-dir /path/to/docs
    
    # 启动定时任务
    python main.py schedule --code-dir /path/to/project --output-dir /path/to/docs --interval 3600
    
    # 查看项目接口列表
    python main.py scan --code-dir /path/to/project
    
    # 查看分析进度
    python main.py status --output-dir /path/to/docs
"""
import os
import sys
import json
import argparse

# 确保可以导入 agentica
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_analyzer.config import AnalyzerConfig
from code_analyzer.code_reader import CodeReader
from code_analyzer.progress_manager import ProgressManager
from code_analyzer.analyzer import CodeAnalyzerAgent
from code_analyzer.scheduler import AnalyzerScheduler


def cmd_scan(args):
    """扫描项目，列出所有接口"""
    config = AnalyzerConfig(
        code_dir=args.code_dir,
        output_dir=args.output_dir or "/tmp/code_analyzer_output"
    )
    
    reader = CodeReader(config)
    
    print(f"🔍 扫描项目: {config.code_dir}\n")
    
    # 扫描项目结构
    project = reader.scan_project()
    print(f"📁 项目统计:")
    print(f"   文件总数: {project['stats']['total_files']}")
    print(f"   语言分布:")
    for lang, count in sorted(project['stats']['by_language'].items(), key=lambda x: -x[1]):
        print(f"      {lang}: {count}")
    
    # 查找接口
    print(f"\n📋 查找接口...")
    endpoints = reader.find_endpoints()
    
    # 按类型分组
    http_endpoints = [ep for ep in endpoints if ep.type == "http"]
    grpc_endpoints = [ep for ep in endpoints if ep.type == "grpc"]
    
    print(f"\n🌐 HTTP 接口 ({len(http_endpoints)} 个):")
    for ep in http_endpoints:
        print(f"   {ep.method:6} {ep.path:40} -> {ep.file_path}:{ep.line_number}")
    
    print(f"\n📡 gRPC 接口 ({len(grpc_endpoints)} 个):")
    for ep in grpc_endpoints:
        service = ep.service_name or "Unknown"
        print(f"   {service}.{ep.name:30} -> {ep.file_path}:{ep.line_number}")
    
    print(f"\n✅ 共发现 {len(endpoints)} 个接口")


def cmd_analyze(args):
    """执行一次分析"""
    config = AnalyzerConfig(
        code_dir=args.code_dir,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        poe_api_key=args.api_key,
        poe_model=args.model,
    )
    
    analyzer = CodeAnalyzerAgent(config)
    
    # 初始化
    analyzer.initialize()
    
    # 运行分析
    result = analyzer.run_batch()
    
    print(f"\n📊 分析结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_schedule(args):
    """启动定时任务"""
    from code_analyzer.scheduler import run_scheduler_cli
    
    # 重新构建参数
    sys.argv = [
        sys.argv[0],
        "--code-dir", args.code_dir,
        "--output-dir", args.output_dir,
        "--interval", str(args.interval),
        "--batch-size", str(args.batch_size),
        "--api-key", args.api_key,
        "--model", args.model,
    ]
    
    run_scheduler_cli()


def cmd_status(args):
    """查看分析进度"""
    config = AnalyzerConfig(
        code_dir=args.code_dir or "/tmp",
        output_dir=args.output_dir
    )
    
    manager = ProgressManager(config)
    
    try:
        summary = manager.get_summary()
        
        print(f"📊 分析进度:")
        print(f"   项目名称: {summary['project_name']}")
        print(f"   总接口数: {summary['total_endpoints']}")
        print(f"   已完成:   {summary['completed']}")
        print(f"   待处理:   {summary['pending']}")
        print(f"   失败:     {summary['failed']}")
        print(f"   进度:     {summary['progress_percent']}%")
        print(f"   最后运行: {summary['last_run'] or '从未'}")
        
        # 列出已完成的文档
        docs = manager.get_completed_docs()
        if docs:
            print(f"\n📄 已生成文档 ({len(docs)} 个):")
            for doc in docs[:10]:
                print(f"   - {doc}")
            if len(docs) > 10:
                print(f"   ... 还有 {len(docs) - 10} 个")
                
    except Exception as e:
        print(f"❌ 无法读取进度: {e}")
        print(f"   请确保 output_dir 正确且包含 analysis_progress.json")


def cmd_reset(args):
    """重置失败的任务"""
    config = AnalyzerConfig(
        code_dir=args.code_dir or "/tmp",
        output_dir=args.output_dir
    )
    
    manager = ProgressManager(config)
    manager.reset_failed()
    
    print("✅ 已重置所有失败的任务为待处理状态")
    
    summary = manager.get_summary()
    print(f"   待处理: {summary['pending']}")


def main():
    parser = argparse.ArgumentParser(
        description="代码接口分析器 - 自动分析项目接口并生成文档",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # scan 命令
    scan_parser = subparsers.add_parser("scan", help="扫描项目，列出所有接口")
    scan_parser.add_argument("--code-dir", required=True, help="代码目录")
    scan_parser.add_argument("--output-dir", help="输出目录（可选）")
    
    # analyze 命令
    analyze_parser = subparsers.add_parser("analyze", help="执行一次分析")
    analyze_parser.add_argument("--code-dir", required=True, help="代码目录")
    analyze_parser.add_argument("--output-dir", required=True, help="输出目录")
    analyze_parser.add_argument("--batch-size", type=int, default=1, help="每批分析数量")
    analyze_parser.add_argument("--api-key", default="W4HQGO1TRCOcZzRv-8vB84REwnexAshVRVVhyZ9dpII", help="Poe API 密钥")
    analyze_parser.add_argument("--model", default="Claude-sonnet", help="使用的模型")
    
    # schedule 命令
    schedule_parser = subparsers.add_parser("schedule", help="启动定时任务")
    schedule_parser.add_argument("--code-dir", required=True, help="代码目录")
    schedule_parser.add_argument("--output-dir", required=True, help="输出目录")
    schedule_parser.add_argument("--interval", type=int, default=3600, help="运行间隔（秒）")
    schedule_parser.add_argument("--batch-size", type=int, default=1, help="每批分析数量")
    schedule_parser.add_argument("--api-key", default="W4HQGO1TRCOcZzRv-8vB84REwnexAshVRVVhyZ9dpII", help="Poe API 密钥")
    schedule_parser.add_argument("--model", default="Claude-sonnet", help="使用的模型")
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查看分析进度")
    status_parser.add_argument("--output-dir", required=True, help="输出目录")
    status_parser.add_argument("--code-dir", help="代码目录（可选）")
    
    # reset 命令
    reset_parser = subparsers.add_parser("reset", help="重置失败的任务")
    reset_parser.add_argument("--output-dir", required=True, help="输出目录")
    reset_parser.add_argument("--code-dir", help="代码目录（可选）")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 执行对应命令
    commands = {
        "scan": cmd_scan,
        "analyze": cmd_analyze,
        "schedule": cmd_schedule,
        "status": cmd_status,
        "reset": cmd_reset,
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()

