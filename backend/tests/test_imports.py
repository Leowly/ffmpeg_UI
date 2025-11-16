"""
验证测试文件的导入是否正常工作
"""
import sys
import os

# 添加项目根目录到 Python 路径
# 确保无论从哪个目录运行测试，都能正确导入backend模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录 (ffmpeg_UI)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_imports():
    """测试关键模块是否能正确导入"""
    try:
        # 测试 CRUD 模块
        import crud
        print("✓ CRUD module imported successfully")

        # 测试模型
        import models
        print("✓ Models module imported successfully")

        # 测试 schema
        import schemas
        print("✓ Schemas module imported successfully")

        # 测试数据库
        import database
        print("✓ Database module imported successfully")

        # 测试处理模块
        import processing
        print("✓ Processing module imported successfully")

        # 测试配置
        import config
        print("✓ Config module imported successfully")

        # 测试特定函数
        from config import reconstruct_file_path
        print("✓ Specific function imported successfully")

        # 测试处理函数
        from processing import run_ffmpeg_process, ConnectionManager
        print("✓ Processing functions imported successfully")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Other error: {e}")
        return False

if __name__ == "__main__":
    print("Testing import system...")
    success = test_imports()
    if success:
        print("\n✓ All imports successful! Test environment is properly configured.")
    else:
        print("\n✗ Import test failed.")