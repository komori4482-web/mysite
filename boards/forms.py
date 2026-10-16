from django import forms

from .models import Comment, Post
from .validators import MAX_FILES_PER_POST, validate_attachment


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """여러 파일을 한 번에 받는 필드 (Django 공식 문서 방식). 결과는 파일 리스트."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            return []
        single_clean = super().clean
        if not isinstance(data, (list, tuple)):
            data = [data]
        return [single_clean(d, initial) for d in data]


class PostForm(forms.ModelForm):
    files = MultipleFileField(
        required=False,
        label="이미지 / 파일 첨부",
        help_text=(
            f"이미지(jpg·png·gif·webp)와 pdf·txt·md·zip·docx·xlsx·pptx 파일, "
            f"파일당 10MB, 글당 최대 {MAX_FILES_PER_POST}개. 첫 번째 이미지가 목록 썸네일이 됩니다."
        ),
    )

    class Meta:
        model = Post
        fields = ("title", "content", "video_url")

    def clean_video_url(self):
        url = self.cleaned_data.get("video_url", "")
        if url and Post(video_url=url).video_embed is None:
            raise forms.ValidationError(
                "지원하지 않는 주소예요. YouTube, Vimeo 또는 .mp4 파일 링크를 넣어주세요."
            )
        return url

    def clean_files(self):
        files = self.cleaned_data.get("files") or []
        existing = self.instance.files.count() if self.instance.pk else 0

        if existing + len(files) > MAX_FILES_PER_POST:
            raise forms.ValidationError(
                f"첨부파일은 글당 최대 {MAX_FILES_PER_POST}개까지예요. (현재 {existing}개 등록됨)"
            )
        for f in files:
            validate_attachment(f)
        return files


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("content",)
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 3, "placeholder": "댓글을 입력하세요", "style": "min-height:90px"}
            ),
        }