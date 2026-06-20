from celery import shared_task

@shared_task
def process_pdf_task(job_id, pdf_path):
    from .views import process_pdf
    process_pdf(job_id, pdf_path)