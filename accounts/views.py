from os.path import splitext

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.db.models import Count
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from .models import User, CompanyProfile
from jobs.models import Job
from applications.models import Application


# =========================================================
# REGISTER
# =========================================================

def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        role = "candidate"

        if not username or not email or not password:
            messages.error(request, "Please fill all required fields.")
            return render(request, "accounts/register.html")

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            return render(request, "accounts/register.html")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "accounts/register.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "accounts/register.html")

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already exists.")
            return render(request, "accounts/register.html")

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
            )
        except IntegrityError:
            messages.error(request, "Username or email already exists.")
            return render(request, "accounts/register.html")

        login(request, user)
        return redirect("candidate_dashboard")

    return render(request, "accounts/register.html")


# =========================================================
# LOGIN
# =========================================================

def user_login(request):
    if request.user.is_authenticated:
        return redirect_after_login(request.user)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect_after_login(user)

        messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")


def redirect_after_login(user):
    if user.is_superuser:
        return redirect("admin_dashboard")

    if user.role == "recruiter":
        return redirect("recruiter_dashboard")

    return redirect("candidate_dashboard")


# =========================================================
# LOGOUT
# =========================================================

def user_logout(request):
    logout(request)
    return redirect("login")


# =========================================================
# CANDIDATE DASHBOARD
# =========================================================

@login_required
def candidate_dashboard(request):
    applications = Application.objects.filter(
        candidate=request.user
    ).select_related("job")

    context = {
        "total_applications": applications.count(),
        "applied_applications": applications.filter(status="applied").count(),
        "shortlisted_applications": applications.filter(status="shortlisted").count(),
        "selected_applications": applications.filter(status="selected").count(),
        "rejected_applications": applications.filter(status="rejected").count(),
        "recent_applications": applications[:5],
    }

    return render(
        request,
        "accounts/candidate_dashboard.html",
        context,
    )


# =========================================================
# RECRUITER DASHBOARD
# =========================================================

@login_required
def recruiter_dashboard(request):
    if request.user.role != "recruiter":
        messages.error(request, "Recruiter access only.")
        return redirect("candidate_dashboard")

    recruiter_jobs = Job.objects.filter(
        recruiter=request.user
    ).annotate(
        application_count=Count("applications")
    )

    recruiter_applications = Application.objects.filter(
        job__recruiter=request.user
    )

    context = {
        "total_jobs": recruiter_jobs.count(),
        "active_jobs": recruiter_jobs.filter(is_active=True).count(),
        "total_applications": recruiter_applications.count(),
        "applied_applications": recruiter_applications.filter(status="applied").count(),
        "shortlisted_applications": recruiter_applications.filter(status="shortlisted").count(),
        "rejected_applications": recruiter_applications.filter(status="rejected").count(),
        "selected_applications": recruiter_applications.filter(status="selected").count(),
        "job_statistics": recruiter_jobs,
        "recruiter_applications": recruiter_applications,
    }

    return render(
        request,
        "accounts/recruiter_dashboard.html",
        context,
    )


# =========================================================
# RECRUITER APPLICATIONS
# =========================================================

@login_required
def recruiter_applications(request):
    if request.user.role != "recruiter":
        messages.error(request, "Recruiter access only.")
        return redirect("candidate_dashboard")

    applications = Application.objects.filter(
        job__recruiter=request.user
    ).select_related(
        "candidate",
        "job",
    ).order_by("-applied_at")

    return render(
        request,
        "accounts/recruiter_applications.html",
        {"applications": applications},
    )


# =========================================================
# UPDATE APPLICATION STATUS
# =========================================================

@login_required
@require_POST
def update_application_status(request, application_id):
    if request.user.role != "recruiter":
        messages.error(request, "You are not authorized to do this.")
        return redirect("candidate_dashboard")

    application = get_object_or_404(
        Application,
        pk=application_id,
        job__recruiter=request.user,
    )

    new_status = request.POST.get("status")

    allowed_statuses = {
        "applied",
        "shortlisted",
        "rejected",
        "selected",
    }

    if new_status not in allowed_statuses:
        messages.error(request, "Invalid application status.")
    else:
        application.status = new_status
        application.save(update_fields=["status", "updated_at"])

        messages.success(
            request,
            f"Application status updated to {application.get_status_display()}.",
        )

    return redirect("recruiter_applications")


# =========================================================
# CANDIDATE PROFILE
# =========================================================

@login_required
def profile(request):
    user = request.user

    if request.method == "POST":
        new_email = request.POST.get("email", "").strip()

        if not new_email:
            messages.error(request, "Email is required.")
            return render(request, "accounts/profile.html")

        try:
            validate_email(new_email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            return render(request, "accounts/profile.html")

        if User.objects.exclude(pk=user.pk).filter(
            email__iexact=new_email
        ).exists():
            messages.error(
                request,
                "This email address is already registered with another account.",
            )
            return render(request, "accounts/profile.html")

        user.email = new_email
        user.phone = request.POST.get("phone", "").strip()
        user.skills = request.POST.get("skills", "").strip()
        user.education = request.POST.get("education", "").strip()

        # Resume upload
        resume = request.FILES.get("resume")

        if resume:
            allowed_extensions = {".pdf", ".doc", ".docx"}
            extension = splitext(resume.name)[1].lower()

            if extension not in allowed_extensions:
                messages.error(
                    request,
                    "Invalid resume format. Upload PDF, DOC or DOCX.",
                )
                return render(request, "accounts/profile.html")

            if resume.size > 5 * 1024 * 1024:
                messages.error(request, "Resume size must not exceed 5 MB.")
                return render(request, "accounts/profile.html")

            user.resume = resume

        # Profile picture upload
        profile_picture = request.FILES.get("profile_picture")

        if profile_picture:
            allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
            extension = splitext(profile_picture.name)[1].lower()

            if extension not in allowed_extensions:
                messages.error(
                    request,
                    "Invalid profile picture format. Upload JPG, JPEG, PNG or WEBP.",
                )
                return render(request, "accounts/profile.html")

            if profile_picture.size > 2 * 1024 * 1024:
                messages.error(
                    request,
                    "Profile picture size must not exceed 2 MB.",
                )
                return render(request, "accounts/profile.html")

            user.profile_picture = profile_picture

        try:
            user.save()
        except IntegrityError:
            messages.error(
                request,
                "This email address is already registered with another account.",
            )
            return render(request, "accounts/profile.html")

        messages.success(request, "Profile updated successfully!")

    return render(
        request,
        "accounts/profile.html",
    )


# =========================================================
# RECRUITER COMPANY PROFILE
# =========================================================

@login_required
def company_profile(request):
    if request.user.role != "recruiter":
        messages.error(request, "Recruiter access only.")
        return redirect("candidate_dashboard")

    company, created = CompanyProfile.objects.get_or_create(
        recruiter=request.user
    )

    if request.method == "POST":
        company.company_name = request.POST.get("company_name", "").strip()
        company.company_email = request.POST.get("company_email", "").strip()
        company.company_phone = request.POST.get("company_phone", "").strip()
        company.website = request.POST.get("website", "").strip()
        company.industry = request.POST.get("industry", "").strip()
        company.company_size = request.POST.get("company_size", "").strip()
        company.location = request.POST.get("location", "").strip()
        company.description = request.POST.get("description", "").strip()

        company_logo = request.FILES.get("company_logo")

        if company_logo:
            allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
            extension = splitext(company_logo.name)[1].lower()

            if extension not in allowed_extensions:
                messages.error(
                    request,
                    "Invalid logo format. Use JPG, JPEG, PNG or WEBP.",
                )
                return render(
                    request,
                    "accounts/company_profile.html",
                    {"company": company},
                )

            if company_logo.size > 2 * 1024 * 1024:
                messages.error(
                    request,
                    "Company logo size must not exceed 2 MB.",
                )
                return render(
                    request,
                    "accounts/company_profile.html",
                    {"company": company},
                )

            company.company_logo = company_logo

        company.save()
        messages.success(request, "Company profile updated successfully!")

    return render(
        request,
        "accounts/company_profile.html",
        {"company": company},
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can access this dashboard.")
        return redirect("login")

    total_users = User.objects.count()
    total_candidates = User.objects.filter(role="candidate").count()
    total_recruiters = User.objects.filter(role="recruiter").count()
    total_jobs = Job.objects.count()
    active_jobs = Job.objects.filter(is_active=True).count()
    total_applications = Application.objects.count()

    context = {
        "total_users": total_users,
        "total_candidates": total_candidates,
        "total_recruiters": total_recruiters,
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "total_applications": total_applications,
        "applied_applications": Application.objects.filter(status="applied").count(),
        "shortlisted_applications": Application.objects.filter(status="shortlisted").count(),
        "selected_applications": Application.objects.filter(status="selected").count(),
        "rejected_applications": Application.objects.filter(status="rejected").count(),
        "recent_users": User.objects.order_by("-date_joined")[:5],
        "recent_jobs": Job.objects.order_by("-created_at")[:5],
        "recent_applications": Application.objects.select_related(
            "candidate",
            "job",
        ).order_by("-applied_at")[:5],
    }

    return render(
        request,
        "accounts/admin_dashboard.html",
        context,
    )


# =========================================================
# ADMIN USERS
# =========================================================

@login_required
def admin_users(request):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can access this page.")
        return redirect("login")

    users = User.objects.all().order_by("-date_joined")

    return render(
        request,
        "accounts/admin_users.html",
        {"users": users},
    )


# =========================================================
# ADMIN ACTIVATE / DEACTIVATE USER
# =========================================================

@login_required
@require_POST
def toggle_user_status(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can change user status.")
        return redirect("login")

    user = get_object_or_404(User, id=user_id)

    if user.id == request.user.id:
        messages.error(request, "You cannot change your own admin status.")
        return redirect("admin_users")

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])

    if user.is_active:
        messages.success(request, f"{user.username} activated successfully.")
    else:
        messages.success(request, f"{user.username} deactivated successfully.")

    return redirect("admin_users")


# =========================================================
# ADMIN JOBS
# =========================================================

@login_required
def admin_jobs(request):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can manage jobs.")
        return redirect("login")

    jobs = Job.objects.select_related(
        "recruiter"
    ).order_by("-created_at")

    return render(
        request,
        "accounts/admin_jobs.html",
        {"jobs": jobs},
    )


# =========================================================
# ADMIN APPLICATIONS
# =========================================================

@login_required
def admin_applications(request):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can manage applications.")
        return redirect("login")

    applications = Application.objects.select_related(
        "candidate",
        "job",
        "job__recruiter",
    ).order_by("-applied_at")

    return render(
        request,
        "accounts/admin_applications.html",
        {"applications": applications},
    )


# =========================================================
# ADMIN REPORTS
# =========================================================

@login_required
def admin_reports(request):
    if not request.user.is_superuser:
        messages.error(request, "Only admin can view reports.")
        return redirect("login")

    job_application_data = Job.objects.annotate(
        application_count=Count("applications")
    ).order_by("-application_count")[:10]

    context = {
        "total_users": User.objects.count(),
        "total_candidates": User.objects.filter(role="candidate").count(),
        "total_recruiters": User.objects.filter(role="recruiter").count(),
        "total_jobs": Job.objects.count(),
        "active_jobs": Job.objects.filter(is_active=True).count(),
        "total_applications": Application.objects.count(),
        "applied_applications": Application.objects.filter(status="applied").count(),
        "shortlisted_applications": Application.objects.filter(status="shortlisted").count(),
        "selected_applications": Application.objects.filter(status="selected").count(),
        "rejected_applications": Application.objects.filter(status="rejected").count(),
        "job_application_data": job_application_data,
    }

    return render(
        request,
        "accounts/admin_reports.html",
        context,
    )


# =========================================================
# ADMIN ANALYTICS DASHBOARD
# =========================================================

@login_required
def admin_analytics_dashboard(request):
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Admin access required.")

    return render(
        request,
        "accounts/admin_analytics_dashboard.html",
    )