"""
统一测试运行器
结合了原来 run_tests.py 和 run_all_tests.py 的功能
"""
import subprocess
import sys
import os
from pathlib import Path


def run_test_directly(test_name, test_file, timeout=120):
    """直接运行单个测试"""
    print(f"\n{'='*50}")
    print(f"运行测试: {test_name}")
    print(f"{'='*50}")

    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent

    try:
        result = subprocess.run([
            sys.executable,
            "-m",
            "pytest",
            str(tests_dir / test_file),
            "-v",
            "--tb=short"
        ], cwd=project_root, capture_output=True, text=True, timeout=timeout)

        print(result.stdout)
        if result.stderr:
            print("错误输出:")
            print(result.stderr)

        if result.returncode == 0:
            print(f"✓ {test_name} 测试通过")
            return True
        else:
            print(f"✗ {test_name} 测试失败，返回码: {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print(f"✗ {test_name} 测试超时")
        return False
    except Exception as e:
        print(f"✗ {test_name} 测试出错: {e}")
        return False


def run_specific_backend_tests():
    """运行特定的后端修改测试（原 run_all_tests.py 的功能）"""
    print("开始运行特定后端修改测试...")

    tests = [
        ("后端修改导入测试", "test_backend_changes.py"),
        ("特定修改验证测试", "test_specific_changes.py"),
        ("多队列功能测试", "test_multi_queue.py"),
        ("多队列功能验证", "validate_multi_queue.py")
    ]

    passed = 0
    total = len(tests)

    for test_name, test_file in tests:
        if run_test_directly(test_name, test_file, timeout=30):  # 使用30秒超时，与原脚本一致
            passed += 1

    print(f"\n{'='*50}")
    print(f"后端修改测试总结: {passed}/{total} 个测试通过")
    print(f"{'='*50}")

    if passed == total:
        print("🎉 所有后端修改测试都通过了！")
        return True
    else:
        print(f"❌ {total - passed} 个后端修改测试失败")
        return False


def run_tests():
    """运行所有测试文件（原 run_tests.py 的功能）"""
    print("开始运行所有测试...")

    # 获取当前脚本的目录（tests目录）
    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent

    # 查找所有测试文件
    test_files = list(tests_dir.glob("test_*.py"))

    if not test_files:
        print("未找到任何测试文件")
        return False

    print(f"找到 {len(test_files)} 个测试文件:")
    for test_file in test_files:
        print(f"  - {test_file.name}")

    results = []
    for test_file in test_files:
        print(f"\n{'='*60}")
        print(f"运行测试: {test_file.name}")
        print(f"{'='*60}")

        try:
            # 运行单个测试文件
            result = subprocess.run([
                sys.executable, "-m", "pytest", str(test_file),
                "-v",  # 详细输出
                "--tb=short"  # 简短的回溯信息
            ], cwd=project_root, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                status = "✓ 通过"
            else:
                status = "✗ 失败"

            print(f"输出:\n{result.stdout}")
            if result.stderr:
                print(f"错误:\n{result.stderr}")

            print(f"\n结果: {status} (返回码: {result.returncode})")
            results.append((test_file.name, result.returncode == 0, result.returncode))

        except subprocess.TimeoutExpired:
            print(f"✗ 测试超时: {test_file.name}")
            results.append((test_file.name, False, -1))
        except Exception as e:
            print(f"✗ 运行测试时出错: {test_file.name}, 错误: {e}")
            results.append((test_file.name, False, -1))

    # 输出总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")

    total_tests = len(results)
    passed_tests = sum(1 for _, passed, _ in results if passed)
    failed_tests = total_tests - passed_tests

    print(f"总测试数: {total_tests}")
    print(f"通过: {passed_tests}")
    print(f"失败: {failed_tests}")

    if failed_tests > 0:
        print("\n失败的测试:")
        for test_name, passed, return_code in results:
            if not passed:
                print(f"  - {test_name} (返回码: {return_code})")

    print(f"\n总体结果: {'✓ 全部通过' if failed_tests == 0 else '✗ 部分失败'}")

    return failed_tests == 0


def run_tests_with_coverage():
    """运行带覆盖率的测试"""
    print("开始运行带覆盖率的测试...")

    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent

    try:
        # 检查是否安装了 coverage
        import coverage
    except ImportError:
        print("coverage 模块未安装，将运行普通测试")
        return run_tests()

    # 查找所有测试文件
    test_files = list(tests_dir.glob("test_*.py"))

    if not test_files:
        print("未找到任何测试文件")
        return False

    print(f"运行带覆盖率的测试，共 {len(test_files)} 个文件...")

    # 配置 coverage
    cov = coverage.Coverage(source=['backend'])
    cov.start()

    results = []
    for test_file in test_files:
        print(f"\n运行测试: {test_file.name}")

        result = subprocess.run([
            sys.executable, "-m", "pytest", str(test_file), "-v"
        ], cwd=project_root, capture_output=True, text=True)

        results.append((test_file.name, result.returncode == 0))

    cov.stop()
    cov.save()

    print("\n代码覆盖率报告:")
    cov.report(show_missing=True)

    # 生成HTML覆盖率报告
    try:
        cov.html_report(directory=tests_dir / "htmlcov")
        print(f"\nHTML覆盖率报告已生成到: {tests_dir / 'htmlcov'}")
    except Exception as e:
        print(f"生成HTML覆盖率报告失败: {e}")

    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    failed_tests = total_tests - passed_tests

    print(f"\n总测试数: {total_tests}")
    print(f"通过: {passed_tests}")
    print(f"失败: {failed_tests}")

    return failed_tests == 0


def list_all_tests():
    """列出所有测试"""
    tests_dir = Path(__file__).parent
    test_files = list(tests_dir.glob("test_*.py"))

    print("所有测试文件:")
    for i, test_file in enumerate(test_files, 1):
        print(f"{i}. {test_file.name}")

    return len(test_files)


def main():
    """主函数"""
    print("FFmpeg UI 统一测试运行器")
    print("=" * 50)

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "list":
            list_all_tests()
        elif command == "coverage":
            success = run_tests_with_coverage()
            sys.exit(0 if success else 1)
        elif command == "specific":
            success = run_specific_backend_tests()
            sys.exit(0 if success else 1)
        elif command == "help":
            print("用法:")
            print("  python run_tests.py              # 运行所有测试")
            print("  python run_tests.py list         # 列出所有测试")
            print("  python run_tests.py specific     # 运行特定后端修改测试")
            print("  python run_tests.py coverage     # 运行带覆盖率的测试")
            print("  python run_tests.py help         # 显示此帮助")
        else:
            print(f"未知命令: {command}")
            print("使用 'python run_tests.py help' 查看帮助")
    else:
        success = run_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()