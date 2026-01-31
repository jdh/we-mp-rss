import threading
from core.print import print_warning
from driver.base import WX_InterFace
import os
import portalocker
from driver.success import Success

def auth():
    # 使用文件锁确保只有一个进程执行
    lock_file = './data/auth_task.lock'
    try:
        with open(lock_file, 'w') as f:
            portalocker.lock(f, portalocker.LOCK_EX | portalocker.LOCK_NB)
            def run_auth():
                wx=WX_InterFace()
                # wx.Token(callback=Success)
                wx.switch_account()
            
            thread = threading.Thread(target=run_auth)
            thread.start()
            thread.join()  # 可选：等待完成
    except portalocker.exceptions.LockException:
        # 其他进程直接返回
        pass

def setup_auth_task(scheduler):
    """
    设置授权定时任务
    
    Args:
        scheduler: 共享的调度器实例
    """
    if str(os.getenv('WE_RSS.AUTH',False))=="True":
        print_warning("启动授权定时任务")
        print("是否开启调试模式:",str(os.getenv('DEBUG',False)))
        if str(os.getenv('DEBUG',False))=="True":
            scheduler.add_cron_job(auth, "*/5 * * * *", job_id="auth_task", tag="授权定时更新")
        else:
            scheduler.add_cron_job(auth, "0 0 */1 * *", job_id="auth_task", tag="授权定时更新")
        print_warning("授权定时任务已添加到调度器")