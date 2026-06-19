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

import os
import json
import uuid
import threading

from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from functools import lru_cache
from pdf2image import convert_from_path
import pytesseract
import platform
import traceback
import re



def home(request):
    return render(request, 'home.html')

def register(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        industry = request.POST.get("industry")
        password = request.POST.get("password")

        # Create Django user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name
        )

        # OPTIONAL: store extra data in your custom model
        UserRegistration.objects.create(
            name=name,
            email=email,
            industry=industry,
            password=password  # not recommended to store again
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



def home(request):

    if request.method == "POST":

        form = ContactForm(request.POST)

        if form.is_valid():

            name = form.cleaned_data["name"]
            email = form.cleaned_data["email"]
            message = form.cleaned_data["message"]

            # Save to CSV
            import csv

            with open("responses.csv", "a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow([name, email, message])

            messages.success(request, "Message sent successfully!")

            return redirect("home")

    else:
        form = ContactForm()

    return render(request, "home.html", {"form": form})




# ------------------------------------
# BASE DIRECTORY
# ------------------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

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

    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

    POPPLER_PATH = (
        r"C:\Users\NAGARANI\Downloads\poppler\poppler-26.02.0\Library\bin"
    )

else:

    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
    POPPLER_PATH = None


# ------------------------------------
# LOAD MODELS ONCE
# ------------------------------------


    


# ------------------------------------
# HOME
# ------------------------------------

def free_trail(request):
    return render(request, "bidbuddy2.html")


# ------------------------------------
# FILE UPLOAD
# ------------------------------------

# ------------------------------------
# LOAD MODELS ONLY WHEN NEEDED
# ------------------------------------

@lru_cache(maxsize=1)
def get_summarizer():
    from transformers import pipeline

    return pipeline(
        "summarization",
        model="Falconsai/text_summarization"
    )


@lru_cache(maxsize=1)
def get_classifier():
    from transformers import pipeline

    return pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli"
    )


@lru_cache(maxsize=1)
def get_compliance_pipe():
    from transformers import pipeline

    return pipeline(
        "text2text-generation",
        model="google/flan-t5-small"
    )

# ------------------------------------
# UPLOAD FILE
# ------------------------------------
def upload_file(request):
    print("PROCESS PDF STARTED")

    if request.method != "POST":
        return JsonResponse({"error": "POST required"})

    if "TenderFile" not in request.FILES:
        return JsonResponse({"error": "No file selected"})

    file = request.FILES["TenderFile"]

    job_id = str(uuid.uuid4())

    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    print("UPLOAD RECEIVED")

    with open(pdf_path, "wb+") as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    print("Uploaded File:", file.name)
    print("Saved Path:", pdf_path)

    process_pdf(job_id, pdf_path)

    return JsonResponse({
        "status": "processing",
        "job_id": job_id
    })


# ------------------------------------
# PROCESS PDF
# ------------------------------------
def process_pdf(job_id, pdf_path):
    try:
        pages = convert_from_path(pdf_path)

        result_data = {
            "summary": f"Pages: {len(pages)}",
            "classification": "OK",
            "compliance": "OK"
        }

    except Exception as e:
        result_data = {
            "summary": str(e),
            "classification": "",
            "compliance": ""
        }

    with open(os.path.join(SUMMARY_FOLDER, f"{job_id}.txt"), "w") as f:
        json.dump(result_data, f)
def check_summary(request, job_id):

    print("Checking job:", job_id)

    summary_path = os.path.join(
        SUMMARY_FOLDER,
        f"{job_id}.txt"
    )

    print("Summary path:", summary_path)
    print("Exists:", os.path.exists(summary_path))

    summary_path = os.path.join(SUMMARY_FOLDER, f"{job_id}.txt")

    if os.path.exists(summary_path):

        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return JsonResponse({
            "ready": True,
            "summary": data["summary"],
            "classification": data["classification"],
            "compliance": data["compliance"]
        })

    return JsonResponse({
        "ready": False
    })