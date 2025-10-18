# D:\32685\code\ffmpeg_UI\run.py
import uvicorn
import asyncio
import sys

# 关键：在 uvicorn 启动和创建任何子进程之前，设置好 Windows 的事件循环策略
if sys.platform == "win32":
    print(">>> Gemini: Setting WindowsProactorEventLoopPolicy for Uvicorn...")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print(">>> Gemini: Policy set.")

if __name__ == "__main__":
    # 这里的 "backend.main:app" 完全匹配你之前手动运行时使用的路径
    # 这会告诉 uvicorn 去加载 backend 包里的 main 模块中的 app 对象
    uvicorn.run(
        "backend.main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True
    )