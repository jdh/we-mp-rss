from jobs.mps import *
from core.print import print_info, print_warning


def register_skill_jobs(scheduler):
    """
    将 skill 系统中的定时任务注册到调度器。

    应在 TaskScheduler 启动前调用。
    """
    from skills import SkillRegistry

    job_skills = SkillRegistry.get_jobs()
    if not job_skills:
        print_info("[Skill] 无定时任务 skill 需要注册")
        return

    for skill in job_skills:
        try:
            scheduler.add_cron_job(
                skill.execute,
                skill.trigger,
                job_id=f"skill_{skill.name}",
                tag=f"skill:{skill.name}"
            )
            print_info(f"[Skill] 已注册定时任务: {skill.name} (trigger={skill.trigger})")
        except Exception as e:
            print_warning(f"[Skill] 注册定时任务失败 {skill.name}: {e}")