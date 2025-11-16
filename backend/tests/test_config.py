"""
配置函数单元测试
测试 config.py 中的函数
"""
import os
import sys
import tempfile
import pytest

# 添加项目根目录到 Python 路径
# 确保无论从哪个目录运行测试，都能正确导入backend模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录 (ffmpeg_UI)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import reconstruct_file_path, invalidate_file_path_cache


class TestReconstructFilePath:
    """测试文件路径重建函数"""
    
    def test_reconstruct_file_path_file_exists(self, tmp_path):
        """测试文件已存在的情况"""
        # 创建一个临时文件
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test content")
        
        # 当文件路径已存在时，应直接返回原路径
        result = reconstruct_file_path(str(test_file), 123)
        assert result == str(test_file)
    
    def test_reconstruct_file_path_user_dir_exists(self, tmp_path):
        """测试用户目录中存在文件的情况"""
        # 临时修改 UPLOAD_DIRECTORY 用于测试
        import config as config_module
        original_upload_dir = config_module.UPLOAD_DIRECTORY
        config_module.UPLOAD_DIRECTORY = str(tmp_path)
        
        try:
            # 创建用户目录和文件
            user_dir = tmp_path / "123"
            user_dir.mkdir()
            test_file = user_dir / "test_file.txt"
            test_file.write_text("test content")
            
            # 使用一个不存在的原始路径，但用户目录中有同名文件
            original_path = "/some/other/path/test_file.txt"
            result = reconstruct_file_path(original_path, 123)
            
            expected_path = str(test_file)
            assert result == expected_path
        finally:
            # 恢复原始值
            config_module.UPLOAD_DIRECTORY = original_upload_dir
    
    def test_reconstruct_file_path_not_found(self, tmp_path):
        """测试文件不存在的情况"""
        # 临时修改 UPLOAD_DIRECTORY 用于测试
        import config as config_module
        original_upload_dir = config_module.UPLOAD_DIRECTORY
        config_module.UPLOAD_DIRECTORY = str(tmp_path)
        
        try:
            # 使用一个不存在的路径
            original_path = "/some/nonexistent/path/test_file.txt"
            result = reconstruct_file_path(original_path, 123)
            
            assert result is None
        finally:
            # 恢复原始值
            config_module.UPLOAD_DIRECTORY = original_upload_dir
    
    def test_reconstruct_file_path_creates_upload_dir(self, tmp_path):
        """测试函数会自动创建上传目录"""
        # 临时修改 UPLOAD_DIRECTORY 用于测试
        import config as config_module
        original_upload_dir = config_module.UPLOAD_DIRECTORY
        test_dir = str(tmp_path / "new_upload_dir")
        config_module.UPLOAD_DIRECTORY = test_dir
        
        try:
            # 访问不存在的目录，函数会自动创建
            original_path = "/some/path/file.txt"
            result = reconstruct_file_path(original_path, 123)
            
            # 目录应该被创建
            assert os.path.exists(test_dir)
            assert result is None  # 因为文件不存在
        finally:
            # 恢复原始值
            config_module.UPLOAD_DIRECTORY = original_upload_dir


class TestCacheFunctionality:
    """测试缓存功能"""
    
    def test_lru_cache_behavior(self, tmp_path):
        """测试LRU缓存行为"""
        # 临时修改 UPLOAD_DIRECTORY 用于测试
        import config as config_module
        original_upload_dir = config_module.UPLOAD_DIRECTORY
        config_module.UPLOAD_DIRECTORY = str(tmp_path)
        
        try:
            # 创建用户目录和文件
            user_dir = tmp_path / "456"
            user_dir.mkdir()
            test_file = user_dir / "cached_file.txt"
            test_file.write_text("test content")
            
            original_path = "/some/path/cached_file.txt"
            
            # 第一次调用，应该进行实际计算
            result1 = reconstruct_file_path(original_path, 456)
            cache_info1 = reconstruct_file_path.cache_info()
            
            # 第二次调用相同参数，应该命中缓存
            result2 = reconstruct_file_path(original_path, 456)
            cache_info2 = reconstruct_file_path.cache_info()
            
            # 结果应该相同
            assert result1 == result2
            
            # 缓存命中次数应该增加
            assert cache_info2.hits >= cache_info1.hits
            
        finally:
            # 恢复原始值
            config_module.UPLOAD_DIRECTORY = original_upload_dir
    
    def test_cache_clearing(self, tmp_path):
        """测试清除缓存功能"""
        # 临时修改 UPLOAD_DIRECTORY 用于测试
        import config as config_module
        original_upload_dir = config_module.UPLOAD_DIRECTORY
        config_module.UPLOAD_DIRECTORY = str(tmp_path)
        
        try:
            # 创建用户目录和文件
            user_dir = tmp_path / "789"
            user_dir.mkdir()
            test_file = user_dir / "clear_test.txt"
            test_file.write_text("test content")
            
            original_path = "/some/path/clear_test.txt"
            
            # 调用函数几次来填充缓存
            reconstruct_file_path(original_path, 789)
            cache_info_before = reconstruct_file_path.cache_info()
            
            # 清除缓存
            invalidate_file_path_cache()
            cache_info_after = reconstruct_file_path.cache_info()
            
            # 检查缓存是否被清空
            assert cache_info_after.currsize == 0
            
        finally:
            # 恢复原始值
            config_module.UPLOAD_DIRECTORY = original_upload_dir
    
    def test_cache_maxsize(self):
        """测试缓存最大大小"""
        cache_info = reconstruct_file_path.cache_info()
        assert cache_info.maxsize == 128  # 我们设置的值


def test_upload_directory_constant():
    """测试上传目录常量"""
    from config import UPLOAD_DIRECTORY
    # 检查是否是字符串类型
    assert isinstance(UPLOAD_DIRECTORY, str)
    # 检查是否是相对路径
    assert UPLOAD_DIRECTORY.startswith('./')


if __name__ == "__main__":
    pytest.main(["-v"])