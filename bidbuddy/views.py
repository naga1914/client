from django.shortcuts import render, redirect
from .models import UserRegistration
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from django.contrib.auth import logout



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