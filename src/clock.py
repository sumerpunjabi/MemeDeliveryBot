from apscheduler.schedulers.blocking import BlockingScheduler
from main import main

sched = BlockingScheduler()


@sched.scheduled_job('cron', day_of_week='mon-sun', hour=0)
def scheduled_job():
    main()


@sched.scheduled_job('cron', day_of_week='mon-sun', hour=3)
def scheduled_job():
    main()


@sched.scheduled_job('cron', day_of_week='mon-sun', hour=6)
def scheduled_job():
    main()


@sched.scheduled_job('cron', day_of_week='mon-sun', hour=9)
def scheduled_job():
    main()


@sched.scheduled_job('cron', day_of_week='mon-sun', hour=12)
def scheduled_job():
    main()


@sched.scheduled_job('cron', day_of_week='mon-sun', hour=15)
def scheduled_job():
    main()


@sched.scheduled_job('cron', day_of_week='mon-sun', hour=18)
def scheduled_job():
    main()


@sched.scheduled_job('cron', day_of_week='mon-sun', hour=21)
def scheduled_job():
    main()


sched.start()
