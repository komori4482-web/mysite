from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse

from .models import Banner, Skill


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 3


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    inlines = [SkillInline]

    def has_add_permission(self, request):
        return not Banner.objects.exists()

    def changelist_view(self, request, extra_context=None):
        # 배너가 있으면 목록 대신 바로 수정 화면으로
        banner = Banner.objects.first()
        if banner:
            return redirect(reverse("admin:boards_banner_change", args=[banner.pk]))
        return super().changelist_view(request, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        messages.success(request, "등록이 완료되었습니다.")
        return redirect(reverse("admin:boards_banner_change", args=[obj.pk]))

    def response_change(self, request, obj):
        messages.success(request, "수정이 완료되었습니다.")
        return redirect(reverse("admin:boards_banner_change", args=[obj.pk]))