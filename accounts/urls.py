from django.urls import path

from . import views
from . import analytics_views


urlpatterns = [

    # =====================================================
    # AUTHENTICATION
    # =====================================================

    path(
        "register/",
        views.register,
        name="register",
    ),

    path(
        "login/",
        views.user_login,
        name="login",
    ),

    path(
        "logout/",
        views.user_logout,
        name="logout",
    ),


    # =====================================================
    # CANDIDATE
    # =====================================================

    path(
        "profile/",
        views.profile,
        name="profile",
    ),

    path(
        "candidate/dashboard/",
        views.candidate_dashboard,
        name="candidate_dashboard",
    ),


    # =====================================================
    # RECRUITER
    # =====================================================

    path(
        "company-profile/",
        views.company_profile,
        name="company_profile",
    ),

    path(
        "recruiter/dashboard/",
        views.recruiter_dashboard,
        name="recruiter_dashboard",
    ),

    path(
        "recruiter/applications/",
        views.recruiter_applications,
        name="recruiter_applications",
    ),

    path(
        "recruiter/applications/<int:application_id>/status/",
        views.update_application_status,
        name="update_application_status",
    ),


    # =====================================================
    # ADMIN
    # =====================================================

    path(
        "admin-dashboard/",
        views.admin_dashboard,
        name="admin_dashboard",
    ),

    path(
        "admin-users/",
        views.admin_users,
        name="admin_users",
    ),

    path(
        "admin-users/toggle/<int:user_id>/",
        views.toggle_user_status,
        name="toggle_user_status",
    ),

    path(
        "admin-jobs/",
        views.admin_jobs,
        name="admin_jobs",
    ),

    path(
        "admin-applications/",
        views.admin_applications,
        name="admin_applications",
    ),

    path(
        "admin-reports/",
        views.admin_reports,
        name="admin_reports",
    ),

    path(
        "admin-analytics/",
        views.admin_analytics_dashboard,
        name="admin_analytics_dashboard",
    ),


    # =====================================================
    # ANALYTICS API
    # =====================================================

    path(
        "api/analytics/dashboard/",
        analytics_views.analytics_dashboard_api,
        name="analytics_dashboard_api",
    ),

]