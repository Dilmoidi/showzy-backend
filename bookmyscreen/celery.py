import os
from celery import Celery

# Set default Django settings module for 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyscreen.settings')

app = Celery('bookmyscreen')

# Load configs using namespace 'CELERY' (CELERY_ broker configs)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Discover tasks inside registered apps (e.g. tasks.py)
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
