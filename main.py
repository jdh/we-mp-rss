import uvicorn
from core.config import cfg
from core.print import print_warning
import threading
import os
import signal
import sys

# 全局调度器实例
scheduler_instance = None

def cleanup_scheduler():
    """清理调度器资源"""
    global scheduler_instance
    if scheduler_instance:
        try:
            print("正在关闭调度器...")
            scheduler_instance.shutdown(wait=False)
        except Exception as e:
            print(f"关闭调度器时出错: {e}")

def signal_handler(signum, frame):
    """处理系统信号"""
    print(f"\n接收到信号 {signum}，正在清理...")
    cleanup_scheduler()
    sys.exit(0)

if __name__ == '__main__':
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("环境变量:")
    for k,v in os.environ.items():
        print(f"{k}={v}")
    if cfg.args.init=="True":
        import init_sys as init
        init.init()
    if  cfg.args.job =="True" and cfg.get("server.enable_job",False):
        from jobs import start_all_task
        from jobs.mps import get_scheduler
        # 获取全局调度器实例
        scheduler_instance = get_scheduler()
        # 使用守护线程，这样主程序退出时线程会自动结束
        job_thread = threading.Thread(target=start_all_task, daemon=True)
        job_thread.start()
    else:
        print_warning("未开启定时任务")
    
    print("启动服务器")
    AutoReload=cfg.get("server.auto_reload",False)
    thread=cfg.get("server.threads",1)
    
    try:
        uvicorn.run("web:app", host="0.0.0.0", port=int(cfg.get("port",8001)),
                reload=AutoReload,
                reload_dirs=['core','web_ui'],
                reload_excludes=['static','web_ui','data'], 
                workers=thread,
                )
    finally:
        cleanup_scheduler()
    pass