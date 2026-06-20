from celery import shared_task
from .views import process_pdf

@shared_task
def process_pdf_task(job_id, pdf_path):
    process_pdf(job_id, pdf_path)