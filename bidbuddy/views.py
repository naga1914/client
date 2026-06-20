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
from functools import lru_cache
from pdf2image import convert_from_path
import pytesseract

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
    POPPLER_PATH = "/usr/bin"  # or None

# ------------------------------------
# MEMORY MONITORING
# ------------------------------------
def check_memory():
    """Check current memory usage"""
    if HAS_PSUTIL:
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            print(f"Current memory usage: {memory_mb:.2f} MB")
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

def load_models():
    """Load AI models with memory optimization"""
    global summarizer, classifier, compliance_pipe
    from transformers import pipeline
    
    check_memory()
    
    try:
        if summarizer is None:
            print("Loading summarizer model...")
            summarizer = pipeline(
                "summarization",
                model="sshleifer/distilbart-cnn-12-6",
                device=-1,  # Force CPU
                model_kwargs={"low_cpu_mem_usage": True}
            )
            gc.collect()
            print("Summarizer loaded")
            check_memory()

        if classifier is None:
            print("Loading classifier model...")
            classifier = pipeline(
                "zero-shot-classification",
                model="valhalla/distilbart-mnli-12-1",
                device=-1,
                model_kwargs={"low_cpu_mem_usage": True}
            )
            gc.collect()
            print("Classifier loaded")
            check_memory()

        if compliance_pipe is None:
            print("Loading compliance model...")
            compliance_pipe = pipeline(
                "text2text-generation",
                model="google/flan-t5-small",
                device=-1,
                model_kwargs={"low_cpu_mem_usage": True}
            )
            gc.collect()
            print("Compliance model loaded")
            check_memory()
            
    except Exception as e:
        print(f"Error loading models: {e}")
        traceback.print_exc()

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

# ------------------------------------
# FILE UPLOAD (OPTIMIZED)
# ------------------------------------
@csrf_exempt
def upload_file(request):
    """Handle file upload with size validation"""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if "TenderFile" not in request.FILES:
        return JsonResponse({"error": "No file selected"}, status=400)

    file = request.FILES["TenderFile"]
    
    # File size validation (max 5MB)
    if file.size > 5 * 1024 * 1024:
        return JsonResponse({
            "error": "File too large. Maximum size is 5MB."
        }, status=400)
    
    # File type validation
    if not file.name.lower().endswith('.pdf'):
        return JsonResponse({
            "error": "Only PDF files are supported."
        }, status=400)

    job_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")

    try:
        with open(pdf_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)
    except Exception as e:
        return JsonResponse({
            "error": f"Failed to save file: {str(e)}"
        }, status=500)

    print(f"Uploaded File: {file.name}")
    print(f"Saved Path: {pdf_path}")
    print(f"File Size: {os.path.getsize(pdf_path)} bytes")
    
    check_memory()

    # Process PDF in background thread to avoid timeout
    thread = threading.Thread(target=process_pdf, args=(job_id, pdf_path))
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        "status": "processing",
        "job_id": job_id
    })

# ------------------------------------
# PROCESS PDF (MEMORY OPTIMIZED)
# ------------------------------------
def process_pdf(job_id, pdf_path):
    """Process PDF with memory optimization"""
    try:
        # Load models only when needed
        load_models()
        check_memory()
        
        print(f"Processing PDF: {pdf_path}")
        print(f"PDF Exists: {os.path.exists(pdf_path)}")

        # Convert only first page with lower DPI
        try:
            pages = convert_from_path(
                pdf_path, 
                poppler_path=POPPLER_PATH,
                first_page=1,
                last_page=1,  # Only first page
                dpi=150,      # Lower DPI for less memory
                fmt='jpeg'    # JPEG uses less memory
            )
        except Exception as e:
            print(f"Conversion error: {e}")
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
        
        # If no text extracted, provide default
        if not extracted_text.strip():
            extracted_text = "No text could be extracted from the PDF. Please ensure the PDF contains readable text."

        # Process with AI models (with error handling)
        result_data = {
            "summary": "",
            "classification": "",
            "compliance": ""
        }

        # ------------------------------------
        # SUMMARY
        # ------------------------------------
        try:
            if summarizer is not None:
                summary_result = summarizer(
                    extracted_text,
                    max_length=60,   # Reduced
                    min_length=15,   # Reduced
                    do_sample=False,
                    truncation=True
                )
                result_data["summary"] = summary_result[0]["summary_text"]
            else:
                result_data["summary"] = "Summarizer model not available"
        except Exception as e:
            print(f"Summary error: {e}")
            result_data["summary"] = "Summary could not be generated"

        # ------------------------------------
        # CLASSIFICATION
        # ------------------------------------
        try:
            if classifier is not None:
                classification_result = classifier(
                    extracted_text,
                    candidate_labels=["buildings", "roads", "dams", "bridges", "water", "construction"],
                    multi_label=False
                )
                result_data["classification"] = (
                    f"Top Category: {classification_result['labels'][0]}\n"
                    f"Confidence: {round(classification_result['scores'][0] * 100, 2)}%"
                )
            else:
                result_data["classification"] = "Classifier model not available"
        except Exception as e:
            print(f"Classification error: {e}")
            result_data["classification"] = "Classification temporarily unavailable"

        # ------------------------------------
        # COMPLIANCE EXTRACTION
        # ------------------------------------
        try:
            if compliance_pipe is not None:
                prompt = f"Extract compliance requirements from this text. Return bullet points only if found, else say 'No compliance requirements found':\n\n{extracted_text[:800]}"
                
                compliance_result = compliance_pipe(
                    prompt,
                    max_new_tokens=80,  # Reduced
                    do_sample=False
                )
                result_data["compliance"] = compliance_result[0]["generated_text"]
            else:
                result_data["compliance"] = "Compliance model not available"
        except Exception as e:
            print(f"Compliance error: {e}")
            result_data["compliance"] = "Compliance extraction temporarily unavailable"

        # Clean up models to free memory
        gc.collect()
        check_memory()

    except Exception as e:
        print("ERROR OCCURRED")
        print(traceback.format_exc())
        
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
        print(f"Results saved to {summary_path}")
    except Exception as e:
        print(f"Error saving results: {e}")

# ------------------------------------
# CHECK STATUS
# ------------------------------------
def check_summary(request, job_id):
    """Check processing status"""
    summary_path = os.path.join(SUMMARY_FOLDER, f"{job_id}.txt")

    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
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
            return JsonResponse({
                "ready": False,
                "error": f"Error reading results: {str(e)}"
            })

    return JsonResponse({
        "ready": False
    })