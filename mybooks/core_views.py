from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_signin
from django.contrib.auth import logout as django_signout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import HttpResponse, redirect, render
from django.views.decorators.http import require_POST


def home(request: HttpRequest) -> HttpResponse:
    return redirect("oauth-flow-test")


def signin(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(request.POST.get("next") or request.GET.get("next") or "oauth-flow-test")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        next_url = request.POST.get("next") or request.GET.get("next") or "oauth-flow-test"

        if user := authenticate(request, username=username, password=password):
            auth_signin(request, user)
            return redirect(next_url)

        messages.error(request, "Invalid username or password")
        return render(request, "signin.html", context={"username": username, "next": next_url})

    next_url = request.GET.get("next") or "oauth-flow-test"
    return render(request, "signin.html", context={"next": next_url})


@require_POST
@login_required
def signout(request: HttpRequest) -> HttpResponseRedirect:
    django_signout(request)
    return HttpResponseRedirect(settings.LOGOUT_REDIRECT_URL)
