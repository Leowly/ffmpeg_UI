import uvicorn
import asyncio
import sys

# 在 Uvicorn 做任何事之前，就设置好正确的事件循环策略
if sys.platform == "win32":
    print(">>> [run.py] Setting WindowsProactorEventLoopPolicy for Uvicorn...")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print(">>> [run.py] Policy successfully set.")

if __name__ == "__main__":
    print(">>> [run.py] Starting Uvicorn server...")
    # 用编程的方式启动 uvicorn
    uvicorn.run(
        "backend.main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True
    )