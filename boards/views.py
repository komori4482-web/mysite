from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import CommentForm, PostForm
from .models import Banner, Comment, Post, PostFile
from .validators import is_image_name


def save_attachments(post, files):
    for f in files:
        PostFile.objects.create(
            post=post,
            file=f,
            original_name=f.name[:255],
            is_image=is_image_name(f.name),  # content_type 이 아니라 검증된 확장자로 판단
        )


class AuthorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """로그인 필수 + 작성자 본인만. 비로그인은 로그인 화면, 타인은 403."""

    def test_func(self):
        return self.get_object().author == self.request.user


# ───────────── 게시글 ─────────────

class PostListView(ListView):
    model = Post
    template_name = "boards/post_list.html"
    context_object_name = "posts"
    paginate_by = 9

    def get_queryset(self):
        return Post.objects.select_related("author__profile").prefetch_related("files")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        banner = Banner.objects.prefetch_related("skills").first()
        groups = {}
        if banner:
            for skill in banner.skills.all():
                groups.setdefault(skill.category, []).append(skill)
        context["banner"] = banner
        context["skill_groups"] = groups.items()
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = "boards/post_detail.html"
    context_object_name = "post"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comment_form"] = CommentForm()
        context["comments"] = (
            self.object.comments.filter(parent__isnull=True)
            .select_related("author__profile")
            .prefetch_related("replies__author__profile")
        )
        return context


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = "boards/post_form.html"
    success_url = reverse_lazy("boards:post_list")

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)
        save_attachments(self.object, form.cleaned_data["files"])
        messages.success(self.request, "글이 등록되었습니다.")
        return response


class PostUpdateView(AuthorRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = "boards/post_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        save_attachments(self.object, form.cleaned_data["files"])
        messages.success(self.request, "글이 수정되었습니다.")
        return response

    def get_success_url(self):
        return reverse("boards:post_detail", args=[self.object.pk])


class PostDeleteView(AuthorRequiredMixin, DeleteView):
    model = Post
    template_name = "boards/post_confirm_delete.html"
    success_url = reverse_lazy("boards:post_list")

    def form_valid(self, form):
        messages.success(self.request, "글이 삭제되었습니다.")
        return super().form_valid(form)


# ───────────── 댓글 / 대댓글 ─────────────

@login_required
@require_POST
def comment_create(request, post_pk):
    post = get_object_or_404(Post, pk=post_pk)
    form = CommentForm(request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user

        parent_id = request.POST.get("parent")
        if parent_id:
            # 같은 글의 최상위 댓글에만 답글 가능 (답글에 답글은 불가)
            comment.parent = get_object_or_404(
                Comment, pk=parent_id, post=post, parent__isnull=True
            )

        comment.save()

    return redirect("boards:post_detail", pk=post.pk)


@login_required
def comment_update(request, pk):
    comment = get_object_or_404(Comment, pk=pk)

    if comment.author != request.user:
        raise PermissionDenied

    if request.method == "POST":
        form = CommentForm(request.POST, instance=comment)

        if form.is_valid():
            form.save()
            messages.success(request, "댓글이 수정되었습니다.")
            return redirect("boards:post_detail", pk=comment.post.pk)
    else:
        form = CommentForm(instance=comment)

    return render(
        request,
        "boards/comment_form.html",
        {"form": form, "comment": comment},
    )


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)

    if comment.author != request.user:
        raise PermissionDenied

    post_pk = comment.post.pk
    comment.delete()
    return redirect("boards:post_detail", pk=post_pk)