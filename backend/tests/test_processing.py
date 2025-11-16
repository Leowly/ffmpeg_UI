"""
处理逻辑单元测试
测试 processing.py 中的所有函数和类
"""
import asyncio
import tempfile
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# 添加项目根目录到 Python 路径
# 确保无论从哪个目录运行测试，都能正确导入backend模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录 (ffmpeg_UI)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from processing import (
    run_ffmpeg_blocking,
    run_ffmpeg_process,
    ConnectionManager,
    user_task_queues
)
import crud, schemas
import subprocess


class TestConnectionManager:
    """测试连接管理器"""
    
    def test_connect_disconnect(self):
        """测试连接和断开连接"""
        manager = ConnectionManager()
        mock_websocket = MagicMock()
        
        # 连接
        asyncio.run(manager.connect(mock_websocket, 123))
        
        # 检查连接是否成功
        assert 123 in manager.active_connections
        assert manager.active_connections[123] == mock_websocket
        
        # 断开连接
        manager.disconnect(123)
        
        # 检查是否断开连接
        assert 123 not in manager.active_connections
    
    def test_send_progress(self):
        """测试发送进度"""
        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        
        # 连接
        asyncio.run(manager.connect(mock_websocket, 123))
        
        # 发送进度
        asyncio.run(manager.send_progress(123, 50, "processing"))
        
        # 验证是否调用了websocket的send_json
        mock_websocket.send_json.assert_called_once_with({"progress": 50, "status": "processing"})
        
        # 测试不带状态的进度
        mock_websocket.reset_mock()
        asyncio.run(manager.send_progress(123, 75))
        mock_websocket.send_json.assert_called_once_with({"progress": 75})
    
    def test_send_progress_to_inactive_connection(self):
        """测试向未激活的连接发送进度"""
        manager = ConnectionManager()
        # 直接尝试发送进度到不存在的连接，不应该抛出异常
        try:
            asyncio.run(manager.send_progress(999, 50))
        except Exception:
            pytest.fail("向未激活的连接发送进度不应该抛出异常")


class TestRunFFmpegBlocking:
    """测试FFmpeg阻塞运行函数"""
    
    @patch('subprocess.Popen')
    def test_run_ffmpeg_blocking_success(self, mock_popen):
        """测试FFmpeg运行成功"""
        # 模拟子进程
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # 表示进程已结束
        mock_proc.returncode = 0  # 成功返回码
        mock_proc.stderr = None
        mock_popen.return_value = mock_proc
        
        # 创建一个事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 测试函数
            success, stderr = run_ffmpeg_blocking(
                ["ffmpeg", "-i", "input.mp4", "output.mp4"],
                task_id=1,
                total_duration=10.0,
                main_loop=loop,
                conn_manager=ConnectionManager()
            )
            
            assert success is True
        finally:
            loop.close()
    
    @patch('subprocess.Popen')
    def test_run_ffmpeg_blocking_failure(self, mock_popen):
        """测试FFmpeg运行失败"""
        # 模拟子进程失败
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # 表示进程已结束
        mock_proc.returncode = 1  # 失败返回码
        mock_proc.stderr = None
        mock_popen.return_value = mock_proc
        
        # 创建一个事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 测试函数
            success, stderr = run_ffmpeg_blocking(
                ["ffmpeg", "-i", "input.mp4", "output.mp4"],
                task_id=1,
                total_duration=10.0,
                main_loop=loop,
                conn_manager=ConnectionManager()
            )
            
            assert success is False
        finally:
            loop.close()


class TestRunFFmpegProcess:
    """测试FFmpeg异步处理函数"""
    
    @pytest.mark.asyncio
    async def test_run_ffmpeg_process_success(self):
        """测试FFmpeg异步处理成功"""
        with patch('backend.processing.run_ffmpeg_blocking') as mock_run_blocking, \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('os.replace'), \
             patch('backend.crud.get_task') as mock_get_task, \
             patch('backend.crud.create_user_file') as mock_create_file, \
             patch('backend.crud.update_task') as mock_update_task:
            
            # 模拟成功执行
            mock_run_blocking.return_value = (True, "FFmpeg output")
            
            # 模拟任务
            mock_task = MagicMock()
            mock_task.owner_id = 1
            mock_get_task.return_value = mock_task
            
            # 模拟创建文件
            mock_new_file = MagicMock()
            mock_new_file.id = 999
            mock_create_file.return_value = mock_new_file
            
            # 调用函数
            manager = ConnectionManager()
            await run_ffmpeg_process(
                task_id=1,
                command_args=["ffmpeg", "-i", "input.mp4", "output.mp4"],
                total_duration=10.0,
                conn_manager=manager,
                temp_output_path="/tmp/temp.mp4",
                final_output_path="/tmp/output.mp4",
                final_display_name="output.mp4"
            )
            
            # 验证任务状态被更新为完成
            mock_update_task.assert_called()
            # 确保至少有一次调用是将状态设为完成
            completed_calls = [call for call in mock_update_task.call_args_list 
                              if call[1].get('status') == 'completed']
            assert len(completed_calls) > 0
    
    @pytest.mark.asyncio
    async def test_run_ffmpeg_process_failure(self):
        """测试FFmpeg异步处理失败"""
        with patch('backend.processing.run_ffmpeg_blocking') as mock_run_blocking, \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('backend.crud.update_task') as mock_update_task:
            
            # 模拟执行失败
            mock_run_blocking.return_value = (False, "FFmpeg error")
            
            # 调用函数
            manager = ConnectionManager()
            await run_ffmpeg_process(
                task_id=1,
                command_args=["ffmpeg", "-i", "input.mp4", "output.mp4"],
                total_duration=10.0,
                conn_manager=manager,
                temp_output_path="/tmp/temp.mp4",
                final_output_path="/tmp/output.mp4",
                final_display_name="output.mp4"
            )
            
            # 验证任务状态被更新为失败
            failed_calls = [call for call in mock_update_task.call_args_list 
                           if call[1].get('status') == 'failed']
            assert len(failed_calls) > 0
    
    @pytest.mark.asyncio
    async def test_run_ffmpeg_process_exception_handling(self):
        """测试FFmpeg异步处理异常处理"""
        with patch('backend.processing.run_ffmpeg_blocking') as mock_run_blocking, \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('backend.crud.update_task') as mock_update_task:
            
            # 模拟执行时抛出异常
            mock_run_blocking.side_effect = Exception("Test error")
            
            # 调用函数
            manager = ConnectionManager()
            await run_ffmpeg_process(
                task_id=1,
                command_args=["ffmpeg", "-i", "input.mp4", "output.mp4"],
                total_duration=10.0,
                conn_manager=manager,
                temp_output_path="/tmp/temp.mp4",
                final_output_path="/tmp/output.mp4",
                final_display_name="output.mp4"
            )
            
            # 验证任务状态被更新为失败
            failed_calls = [call for call in mock_update_task.call_args_list 
                           if call[1].get('status') == 'failed']
            assert len(failed_calls) > 0
    
    @pytest.mark.asyncio
    async def test_run_ffmpeg_process_cleanup_in_finally(self):
        """测试FFmpeg处理完成后的清理操作"""
        with patch('backend.processing.run_ffmpeg_blocking') as mock_run_blocking, \
             patch('os.path.exists', return_value=True) as mock_exists, \
             patch('os.remove') as mock_remove, \
             patch('os.replace'), \
             patch('backend.crud.get_task') as mock_get_task, \
             patch('backend.crud.create_user_file') as mock_create_file, \
             patch('backend.crud.update_task'):
            
            # 模拟成功执行
            mock_run_blocking.return_value = (True, "FFmpeg output")
            
            # 模拟任务
            mock_task = MagicMock()
            mock_task.owner_id = 1
            mock_get_task.return_value = mock_task
            
            # 模拟创建文件
            mock_new_file = MagicMock()
            mock_new_file.id = 999
            mock_create_file.return_value = mock_new_file
            
            # 调用函数
            manager = ConnectionManager()
            await run_ffmpeg_process(
                task_id=1,
                command_args=["ffmpeg", "-i", "input.mp4", "output.mp4"],
                total_duration=10.0,
                conn_manager=manager,
                temp_output_path="/tmp/temp.mp4",
                final_output_path="/tmp/output.mp4",
                final_display_name="output.mp4"
            )
            
            # 验证临时文件被清理（在finally块中）
            assert mock_remove.called


class TestUserTaskQueues:
    """测试用户任务队列"""
    
    def test_user_queues_creation(self):
        """测试用户队列的创建"""
        # 访问不存在的用户队列，应该自动创建
        user_queue = user_task_queues[12345]
        assert user_queue is not None
        assert user_queue.qsize() == 0
    
    def test_user_queues_isolation(self):
        """测试用户队列的隔离性"""
        # 添加任务到不同用户的队列
        task1 = {"task_id": 1, "owner_id": 1001, "command": "task1"}
        task2 = {"task_id": 2, "owner_id": 1002, "command": "task2"}
        
        asyncio.run(user_task_queues[1001].put(task1))
        asyncio.run(user_task_queues[1002].put(task2))
        
        # 验证队列隔离
        assert user_task_queues[1001].qsize() == 1
        assert user_task_queues[1002].qsize() == 1
        
        # 从队列中取出任务
        retrieved_task1 = asyncio.run(user_task_queues[1001].get())
        retrieved_task2 = asyncio.run(user_task_queues[1002].get())
        
        assert retrieved_task1["task_id"] == 1
        assert retrieved_task2["task_id"] == 2


if __name__ == "__main__":
    pytest.main(["-v"])