#!/usr/bin/env python
"""回归测试运行器。

一键运行所有回归测试，支持 pytest 参数传递。

使用方法：
    python tests/run_all.py                    # 运行全部测试
    python tests/run_all.py -v                  # 详细输出
    python tests/run_all.py -k "login"          # 筛选测试
    python tests/run_all.py --keep-db           # 不清理测试数据（调试用）
"""

import os
import sys
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(description="回归测试运行器")
    parser.add_argument("--api-base", default=os.environ.get("API_BASE_URL", "http://localhost:8000"),
                        help="后端 API 地址 (默认: http://localhost:8000)")
    parser.add_argument("--keep-db", action="store_true",
                        help="保留测试数据库（不执行 seed 重置）")
    parser.add_argument("pytest_args", nargs="*",
                        help="传递给 pytest 的参数")

    args, unknown = parser.parse_known_args()

    # 设置环境变量
    os.environ.setdefault("API_BASE_URL", args.api_base)
    os.environ.setdefault("RATE_LIMIT_ENABLED", "0")  # 测试时关闭速率限制

    # 检查服务状态
    import requests
    try:
        r = requests.get(f"{args.api_base}/api/health", timeout=5)
        if r.status_code != 200 or r.json().get("status") != "ok":
            print(f"⚠️  后端服务 {args.api_base} 状态异常")
            sys.exit(1)
        print(f"✅ 后端服务 {args.api_base} 状态正常")
    except Exception as e:
        print(f"❌ 无法连接后端服务 {args.api_base}: {e}")
        print("请确保后端已启动：cd backend && python migrate.py && uvicorn app.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

    # 构建 pytest 参数
    tests_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    pytest_cmd = ["python", "-m", "pytest", tests_dir, "-v"]

    if args.pytest_args:
        pytest_cmd.extend(args.pytest_args)
    if unknown:
        pytest_cmd.extend(unknown)

    print(f"\n{'='*60}")
    print(f"回归测试套件 — 暑假作业打卡系统")
    print(f"{'='*60}")
    print(f"API 地址: {args.api_base}")
    print(f"测试目录: {tests_dir}")
    print(f"命令: {' '.join(pytest_cmd)}")
    print()

    # 运行测试
    result = subprocess.run(pytest_cmd, cwd=tests_dir)

    # 输出统计
    print(f"\n{'='*60}")
    if result.returncode == 0:
        print("✅ 所有回归测试通过！")
    else:
        print(f"❌ 测试失败，退出码: {result.returncode}")
    print(f"{'='*60}")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
