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
import requests

HF_API_KEY = settings.HF_API_KEY

HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}"
}

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

def upload_file(request):
    if request.method == "POST" and request.FILES.get("document"):

        uploaded_file = request.FILES["document"]

        job_id = str(uuid.uuid4())

        return JsonResponse({
            "job_id": job_id
        })

    return JsonResponse({
        "error": "No file uploaded"
    }, status=400)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
SUMMARY_FOLDER = os.path.join(BASE_DIR, "summaries")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SUMMARY_FOLDER, exist_ok=True)

from django.http import JsonResponse

def check_summary(request, job_id):
    return JsonResponse({
        "ready": True,
        "summary": "Sample tender summary",
        "classification": "Construction - 95%",
        "compliance": "GST registration required"
    })
    
def get_summary(text):
    API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

    response = requests.post(
        API_URL,
        headers=HEADERS,
        json={
            "inputs": text[:1500],
            "parameters": {
                "max_length": 60,
                "min_length": 15
            }
        }
    )

    data = response.json()

    if isinstance(data, list):
        return data[0]["summary_text"]

    return "Summary generation failed"


def get_classification(text):
    API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"

    response = requests.post(
        API_URL,
        headers=HEADERS,
        json={
            "inputs": text,
            "parameters": {
                "candidate_labels": [
                    "buildings",
                    "roads",
                    "dams",
                    "bridges",
                    "water",
                    "construction"
                ]
            }
        }
    )

    data = response.json()

    if "labels" in data:
        return (
            f"Top Category: {data['labels'][0]}\n"
            f"Confidence: {round(data['scores'][0] * 100, 2)}%"
        )

    return "Classification failed"


def get_compliance(text):
    API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-small"

    prompt = f"""
Extract compliance requirements from this text.
Return bullet points only.
If none exist, say:
No compliance requirements found.

{text[:800]}
"""

    response = requests.post(
        API_URL,
        headers=HEADERS,
        json={
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 80
            }
        }
    )

    data = response.json()

    if isinstance(data, list):
        return data[0]["generated_text"]

    return "Compliance extraction failed"