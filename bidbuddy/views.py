from django.shortcuts import render, redirect
from .models import UserRegistration
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.core.mail import send_mail
from django.contrib import messages
from .forms import ContactForm
from django.conf import settings
from django.contrib import admin
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse

import os
import json
import uuid
import threading
import gc
import sys
import platform
import traceback
import re
import csv
import logging
from functools import lru_cache
from pdf2image import convert_from_path
import pytesseract

# Setup logging
logger = logging.getLogger(__name__)

# Try to import psutil for memory monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Celery import (optional)
try:
    from celery import shared_task
except ImportError:
    pass

# ------------------------------------
# BASE DIRECTORY
# ------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------
# FOLDERS
# ------------------------------------
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
SUMMARY_FOLDER = os.path.join(BASE_DIR, "summaries")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SUMMARY_FOLDER, exist_ok=True)

# ------------------------------------
# TESSERACT + POPPLER
# ------------------------------------
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    POPPLER_PATH = r"C:\Users\NAGARANI\Downloads\poppler\poppler-26.02.0\Library\bin"
else:
    # Linux (Render)
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
    POPPLER_PATH = None  # Let system find poppler

# ------------------------------------
# MEMORY MONITORING
# ------------------------------------
def check_memory():
    """Check current memory usage"""
    if HAS_PSUTIL:
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            logger.info(f"Current memory usage: {memory_mb:.2f} MB")
            return memory_mb
        except:
            pass
    return None

# ------------------------------------
# GLOBAL MODELS (LOAD ONCE)
# ------------------------------------
summarizer = None
classifier = None
compliance_pipe = None
models_loading = False

def load_models():
    """Load AI models with memory optimization"""
    global summarizer, classifier, compliance_pipe, models_loading
    
    # Prevent multiple simultaneous loading attempts
    if models_loading:
        logger.info("Models already loading, skipping...")
        return
    
    models_loading = True
    
    try:
        from transformers import pipeline
        
        logger.info("Starting model loading...")
        check_memory()
        
        if summarizer is None:
            logger.info("Loading summarizer model...")
            try:
                summarizer = pipeline(
                    "summarization",
                    model="sshleifer/distilbart-cnn-12-6",
                    device=-1,  # Force CPU
                    model_kwargs={"low_cpu_mem_usage": True}
                )
                gc.collect()
                logger.info("Summarizer loaded successfully")
                check_memory()
            except Exception as e:
                logger.error(f"Failed to load summarizer: {str(e)}")
                summarizer = None

        if classifier is None:
            logger.info("Loading classifier model...")
            try:
                classifier = pipeline(
                    "zero-shot-classification",
                    model="valhalla/distilbart-mnli-12-1",
                    device=-1,
                    model_kwargs={"low_cpu_mem_usage": True}
                )
                gc.collect()
                logger.info("Classifier loaded successfully")
                check_memory()
            except Exception as e:
                logger.error(f"Failed to load classifier: {str(e)}")
                classifier = None

        if compliance_pipe is None:
            logger.info("Loading compliance model...")
            try:
                compliance_pipe = pipeline(
                    "text2text-generation",
                    model="google/flan-t5-small",
                    device=-1,
                    model_kwargs={"low_cpu_mem_usage": True}
                )
                gc.collect()
                logger.info("Compliance model loaded successfully")
                check_memory()
            except Exception as e:
                logger.error(f"Failed to load compliance model: {str(e)}")
                compliance_pipe = None
                
    except Exception as e:
        logger.error(f"CRITICAL ERROR loading models: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        models_loading = False

# ------------------------------------
# VIEWS
# ------------------------------------
def home(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            email = form.cleaned_data["email"]
            message = form.cleaned_data["message"]
            
            with open("responses.csv", "a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow([name, email, message])
            
            messages.success(request, "Message sent successfully!")
            return redirect("home")
    else:
        form = ContactForm()
    
    return render(request, "home.html", {"form": form})

def register(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        industry = request.POST.get("industry")
        password = request.POST.get("password")

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name
        )

        UserRegistration.objects.create(
            name=name,
            email=email,
            industry=industry,
            password=password
        )

        return redirect('success')
    return render(request, 'register.html')

def login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            auth_login(request, user)
            return redirect('home')
        else:
            return render(request, 'login.html', {
                'error': 'Invalid Email or Password'
            })
    return render(request, 'login.html')

def success(request):
    return render(request, 'successful.html')

@login_required
def profile(request):
    return render(request, "profile.html")

def logout_view(request):
    logout(request)
    return redirect('home')

def bidbuddy_trial(request):
    return render(request, "bidbuddy2.html")

def pro_version(request):
    return render(request, "pro_version.html")

def pay(request):
    if request.method == "POST":
        return redirect("payment_success")
    return render(request, "payment.html")

def payment_success(request):
    return render(request, "payment_success.html")

def free_trail(request):
    return render(request, "bidbuddy2.html")

def health_check(request):
    """Health check endpoint for Render"""
    memory_info = {}
    if HAS_PSUTIL:
        try:
            process = psutil.Process()
            memory_info = {
                "memory_usage_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                "memory_percent": process.memory_percent()
            }
        except:
            pass
    
    return JsonResponse({
        "status": "ok",
        "memory": memory_info,
        "models_loaded": {
            "summarizer": summarizer is not None,
            "classifier": classifier is not None,
            "compliance": compliance_pipe is not None
        }
    })

def test_upload(request):
    """Test endpoint to verify upload functionality"""
    return JsonResponse({
        "status": "ok",
        "message": "Upload endpoint is accessible",
        "upload_folder_exists": os.path.exists(UPLOAD_FOLDER),
        "upload_folder_writable": os.access(UPLOAD_FOLDER, os.W_OK),
        "summary_folder_exists": os.path.exists(SUMMARY_FOLDER),
        "summary_folder_writable": os.access(SUMMARY_FOLDER, os.W_OK)
    })

# ------------------------------------
# FILE UPLOAD (OPTIMIZED)
# ------------------------------------
@csrf_exempt
def upload_file(request):
    """Handle file upload with size validation and detailed logging"""
    try:
        logger.info("=== UPLOAD REQUEST STARTED ===")
        logger.info(f"Request method: {request.method}")
        
        if request.method != "POST":
            logger.warning("Not a POST request")
            return JsonResponse({"error": "POST required"}, status=405)

        if "TenderFile" not in request.FILES:
            logger.warning("No file in request")
            return JsonResponse({"error": "No file selected"}, status=400)

        file = request.FILES["TenderFile"]
        logger.info(f"File received: {file.name}")
        logger.info(f"File size: {file.size} bytes")
        logger.info(f"File content type: {file.content_type}")
        
        # File size validation (max 5MB)
        if file.size > 5 * 1024 * 1024:
            logger.warning(f"File too large: {file.size} bytes")
            return JsonResponse({
                "error": "File too large. Maximum size is 5MB."
            }, status=400)
        
        # File type validation
        if not file.name.lower().endswith('.pdf'):
            logger.warning(f"Invalid file type: {file.name}")
            return JsonResponse({
                "error": "Only PDF files are supported."
            }, status=400)

        job_id = str(uuid.uuid4())
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"PDF path: {pdf_path}")

        # Save file
        try:
            with open(pdf_path, "wb+") as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            logger.info(f"File saved successfully. Size: {os.path.getsize(pdf_path)} bytes")
        except Exception as e:
            logger.error(f"Failed to save file: {str(e)}")
            logger.error(traceback.format_exc())
            return JsonResponse({
                "error": f"Failed to save file: {str(e)}"
            }, status=500)

        # Start processing in background
        try:
            logger.info("Starting PDF processing thread")
            thread = threading.Thread(target=process_pdf, args=(job_id, pdf_path))
            thread.daemon = True
            thread.start()
            logger.info("PDF processing thread started")
        except Exception as e:
            logger.error(f"Failed to start processing thread: {str(e)}")
            logger.error(traceback.format_exc())
            return JsonResponse({
                "error": f"Failed to start processing: {str(e)}"
            }, status=500)
        
        check_memory()
        
        return JsonResponse({
            "status": "processing",
            "job_id": job_id
        })
        
    except Exception as e:
        logger.error(f"UNHANDLED ERROR in upload_file: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            "error": f"Server error: {str(e)}"
        }, status=500)

# ------------------------------------
# PROCESS PDF (MEMORY OPTIMIZED)
# ------------------------------------
def process_pdf(job_id, pdf_path):
    """Process PDF with memory optimization"""
    result_data = {
        "summary": "Processing started...",
        "classification": "Processing...",
        "compliance": "Processing..."
    }
    
    try:
        logger.info(f"Starting PDF processing for job: {job_id}")
        
        # Load models only when needed
        load_models()
        check_memory()
        
        logger.info(f"Processing PDF: {pdf_path}")
        logger.info(f"PDF Exists: {os.path.exists(pdf_path)}")

        # Convert only first page with lower DPI
        try:
            logger.info("Converting PDF to image...")
            pages = convert_from_path(
                pdf_path, 
                poppler_path=POPPLER_PATH,
                first_page=1,
                last_page=1,  # Only first page
                dpi=150,      # Lower DPI for less memory
                fmt='jpeg'    # JPEG uses less memory
            )
            logger.info(f"Converted {len(pages)} pages")
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            # Fallback to default
            pages = convert_from_path(
                pdf_path, 
                poppler_path=POPPLER_PATH,
                first_page=1,
                last_page=1
            )

        if not pages:
            raise ValueError("No pages could be extracted from PDF")

        extracted_text = ""
        
        # Process each page
        logger.info("Starting OCR...")
        for page in pages:
            text = pytesseract.image_to_string(
                page,
                config='--psm 6 --oem 3'  # Optimized OCR settings
            )
            extracted_text += text + "\n"
            del page  # Free memory immediately
        
        # Force garbage collection
        gc.collect()
        check_memory()

        # Clean and limit text
        clean_text = re.sub(r'\s+', ' ', extracted_text).strip()
        extracted_text = clean_text[:1500]  # Reduced from 4000
        logger.info(f"Extracted text length: {len(extracted_text)} characters")
        
        # If no text extracted, provide default
        if not extracted_text.strip():
            extracted_text = "No text could be extracted from the PDF. Please ensure the PDF contains readable text."

        # ------------------------------------
        # SUMMARY
        # ------------------------------------
        try:
            if summarizer is not None:
                logger.info("Generating summary...")
                summary_result = summarizer(
                    extracted_text,
                    max_length=60,
                    min_length=15,
                    do_sample=False,
                    truncation=True
                )
                result_data["summary"] = summary_result[0]["summary_text"]
                logger.info("Summary generated successfully")
            else:
                result_data["summary"] = "Summarizer model not available"
                logger.warning("Summarizer model is None")
        except Exception as e:
            logger.error(f"Summary error: {e}")
            result_data["summary"] = "Summary could not be generated"

        # ------------------------------------
        # CLASSIFICATION
        # ------------------------------------
        try:
            if classifier is not None:
                logger.info("Generating classification...")
                classification_result = classifier(
                    extracted_text,
                    candidate_labels=["buildings", "roads", "dams", "bridges", "water", "construction"],
                    multi_label=False
                )
                result_data["classification"] = (
                    f"Top Category: {classification_result['labels'][0]}\n"
                    f"Confidence: {round(classification_result['scores'][0] * 100, 2)}%"
                )
                logger.info("Classification generated successfully")
            else:
                result_data["classification"] = "Classifier model not available"
                logger.warning("Classifier model is None")
        except Exception as e:
            logger.error(f"Classification error: {e}")
            result_data["classification"] = "Classification temporarily unavailable"

        # ------------------------------------
        # COMPLIANCE EXTRACTION
        # ------------------------------------
        try:
            if compliance_pipe is not None:
                logger.info("Extracting compliance...")
                prompt = f"Extract compliance requirements from this text. Return bullet points only if found, else say 'No compliance requirements found':\n\n{extracted_text[:800]}"
                
                compliance_result = compliance_pipe(
                    prompt,
                    max_new_tokens=80,
                    do_sample=False
                )
                result_data["compliance"] = compliance_result[0]["generated_text"]
                logger.info("Compliance extracted successfully")
            else:
                result_data["compliance"] = "Compliance model not available"
                logger.warning("Compliance model is None")
        except Exception as e:
            logger.error(f"Compliance error: {e}")
            result_data["compliance"] = "Compliance extraction temporarily unavailable"

        # Clean up models to free memory
        gc.collect()
        check_memory()
        logger.info("PDF processing completed successfully")

    except Exception as e:
        logger.error("ERROR OCCURRED IN PROCESS_PDF")
        logger.error(traceback.format_exc())
        
        result_data = {
            "summary": f"Error: {str(e)}",
            "classification": "Processing failed",
            "compliance": "Processing failed"
        }

    # Save result
    try:
        summary_path = os.path.join(SUMMARY_FOLDER, f"{job_id}.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f)
        logger.info(f"Results saved to {summary_path}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")

# ------------------------------------
# CHECK STATUS
# ------------------------------------
def check_summary(request, job_id):
    """Check processing status"""
    logger.info(f"Checking status for job: {job_id}")
    summary_path = os.path.join(SUMMARY_FOLDER, f"{job_id}.txt")

    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            logger.info(f"Found results for job: {job_id}")
            
            # Check if there was an error
            if "Error" in data.get("summary", ""):
                return JsonResponse({
                    "ready": True,
                    "error": data["summary"],
                    "summary": "Processing failed. Please try a smaller file.",
                    "classification": "",
                    "compliance": ""
                })
            
            return JsonResponse({
                "ready": True,
                "summary": data.get("summary", "No summary available"),
                "classification": data.get("classification", ""),
                "compliance": data.get("compliance", "")
            })
        except Exception as e:
            logger.error(f"Error reading results: {e}")
            return JsonResponse({
                "ready": False,
                "error": f"Error reading results: {str(e)}"
            })

    logger.info(f"No results found for job: {job_id}")
    return JsonResponse({
        "ready": False
    })