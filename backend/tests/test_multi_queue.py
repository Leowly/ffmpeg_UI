#!/usr/bin/env python3
"""
测试多用户多队列功能
"""

import asyncio

from backend.processing import user_task_queues

async def test_multi_user_queues():
    """测试多用户队列功能"""
    print("测试多用户队列功能...")
    
    # 模拟不同用户添加任务到各自的队列
    task1 = {"task_id": 1, "owner_id": 1001, "command": "test_cmd_1"}
    task2 = {"task_id": 2, "owner_id": 1002, "command": "test_cmd_2"}
    task3 = {"task_id": 3, "owner_id": 1001, "command": "test_cmd_3"}
    
    # 添加任务到不同用户的队列
    await user_task_queues[1001].put(task1)
    await user_task_queues[1002].put(task2)
    await user_task_queues[1001].put(task3)
    
    print(f"用户1001队列大小: {user_task_queues[1001].qsize()}")
    print(f"用户1002队列大小: {user_task_queues[1002].qsize()}")
    
    # 从用户1001的队列中取出任务
    retrieved_task1 = await user_task_queues[1001].get()
    print(f"从用户1001队列取出任务: {retrieved_task1['task_id']}")
    user_task_queues[1001].task_done()
    
    retrieved_task3 = await user_task_queues[1001].get()
    print(f"从用户1001队列取出任务: {retrieved_task3['task_id']}")
    user_task_queues[1001].task_done()
    
    # 从用户1002的队列中取出任务
    retrieved_task2 = await user_task_queues[1002].get()
    print(f"从用户1002队列取出任务: {retrieved_task2['task_id']}")
    user_task_queues[1002].task_done()
    
    print(f"用户1001队列大小: {user_task_queues[1001].qsize()}")
    print(f"用户1002队列大小: {user_task_queues[1002].qsize()}")
    
    print("✓ 多用户队列功能测试成功!")

def test_defaultdict_behavior():
    """测试默认字典行为"""
    print("\n测试默认字典行为...")
    
    # 访问不存在的用户队列应该自动创建
    queue_size = user_task_queues[9999].qsize()
    print(f"访问不存在的用户9999的队列大小: {queue_size}")
    print("✓ 默认字典行为正常!")

if __name__ == "__main__":
    print("开始测试多用户多队列功能...")
    asyncio.run(test_multi_user_queues())
    test_defaultdict_behavior()
    print("\n🎉 多用户多队列功能测试完成!")