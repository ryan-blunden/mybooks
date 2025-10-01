from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_signin
from django.contrib.auth import logout as django_signout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import HttpResponse, redirect, render
from django.views.decorators.http import require_POST


def home(request: HttpRequest) -> HttpResponse:
    return redirect("oauth-apps")


def signin(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(request.POST.get("next") or request.GET.get("next") or "oauth-apps")

    if request.method == "POST":
        username = request.POST.get("username").strip()
        password = request.POST.get("password")
        next_url = request.POST.get("next") or request.GET.get("next") or "oauth-apps"

        if user := authenticate(request, username=username, password=password):
            auth_signin(request, user)
            return redirect(next_url)

        messages.error(request, "Invalid username or password")
        return render(request, "signin.html", context={"username": username, "next": next_url})

    next_url = request.GET.get("next") or "oauth-apps"
    return render(request, "signin.html", context={"next": next_url})


def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(request.POST.get("next") or request.GET.get("next") or "oauth-apps")

    next_url = request.POST.get("next") or request.GET.get("next") or "oauth-apps"

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_signin(request, user)
            messages.success(request, "Account created successfully!")
            return redirect(next_url)
    else:
        form = UserCreationForm()

    return render(request, "signup.html", {"form": form, "next": next_url})


@require_POST
@login_required
def signout(request: HttpRequest) -> HttpResponseRedirect:
    django_signout(request)
    return HttpResponseRedirect(settings.LOGOUT_REDIRECT_URL)
