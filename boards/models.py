# boards/models.py
from django.conf import settings
from django.db import models
import re
from urllib.parse import urlparse, parse_qs

class Post(models.Model):

    """
    게시글 CRUD 대상 모델
    """
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name="작성자",
    )
    title = models.CharField(
        "제목",
        max_length=200,
    )
    content = models.TextField(
        "내용",
    )
    created_at = models.DateTimeField(
        "작성일",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "수정일",
        auto_now=True,
    )
    video_url = models.URLField(
        "영상 링크", 
        blank=True, 
        help_text="YouTube, Vimeo 주소 " \
        "또는 .mp4 파일 링크")

    @property
    def video_embed(self):
        """('iframe' 또는 'video', 재생 주소)를 반환. 지원하지 않는 주소면 None."""
        url = self.video_url.strip()
        if not url:
            return None
        p = urlparse(url)
        host = p.netloc.lower().removeprefix("www.").removeprefix("m.")

        # YouTube
        vid = None
        if host == "youtu.be":
            vid = p.path.strip("/").split("/")[0]
        elif host in ("youtube.com", "music.youtube.com"):
            if p.path == "/watch":
                vid = parse_qs(p.query).get("v", [None])[0]
            elif p.path.startswith(("/shorts/", "/embed/", "/live/")):
                parts = p.path.split("/")
                vid = parts[2] if len(parts) > 2 else None
        if vid and re.fullmatch(r"[\w-]{11}", vid):
            return ("iframe", f"https://www.youtube-nocookie.com/embed/{vid}")

        # Vimeo
        if host == "vimeo.com":
            m = re.fullmatch(r"/(\d+)", p.path)
            if m:
                return ("iframe", f"https://player.vimeo.com/video/{m.group(1)}")

        # 직접 올린 영상 파일
        if p.path.lower().endswith((".mp4", ".webm", ".ogg")):
            return ("video", url)

        return None
    
    @property
    def video_thumb(self):
        """목록 카드용 썸네일. ('image' 또는 'video', 주소) 반환, 영상이 없으면 None."""
        e = self.video_embed
        if not e:
            return None
        kind, url = e
        if kind == "video":
            return ("video", url)
        vid = url.rsplit("/", 1)[-1]
        if "youtube" in url:
            return ("image", f"https://img.youtube.com/vi/{vid}/hqdefault.jpg")
        return ("image", f"https://vumbnail.com/{vid}.jpg")
    
    class Meta:
        db_table = "boards_post"
        verbose_name = "게시글"
        verbose_name_plural = "게시글 목록"
        ordering = ["-created_at"]

        def __str__(self):
            return self.title




class PostFile(models.Model):
    """
    게시글에 첨부되는 이미지 또는 일반 파일
    하나의 게시글에 여러 개 첨부 가능
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name="게시글",
    )
    file = models.FileField(
        "첨부 파일",
        upload_to="post_files/%Y/%m/",
    )
    original_name = models.CharField(
        "원본 파일명",
        max_length=255,
    )
    is_image = models.BooleanField(
        "이미지 여부",
        default=False,
    )
    uploaded_at = models.DateTimeField(
        "업로드일",
        auto_now_add=True,
    )

    class Meta:
        db_table = "boards_postfile"
        verbose_name = "게시글 첨부파일"
        verbose_name_plural = "게시글 첨부파일 목록"

    def __str__(self):
        return self.original_name


class Comment(models.Model):
    """
    댓글 CRUD 대상 모델
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="게시글",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="작성자",
    )
    content = models.TextField(
        "내용",
    )
    created_at = models.DateTimeField(
        "작성일",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "수정일",
        auto_now=True,
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        verbose_name="상위 댓글",
    )

    class Meta:
        db_table = "boards_comment"
        verbose_name = "댓글"
        verbose_name_plural = "댓글 목록"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} - {self.post.title}"

class Banner(models.Model):
    """목록 첫 페이지 상단 소개 배너 (1개만 사용)"""
    name = models.CharField("이름", max_length=50)
    role = models.CharField("직무/한 줄 소개", max_length=100, blank=True)
    intro = models.TextField("자기소개", blank=True)
    avatar = models.ImageField("프로필 사진", upload_to="banner/", blank=True, null=True)
    github_url = models.URLField("GitHub 주소", blank=True)
    email = models.EmailField("이메일", blank=True)

    class Meta:
        db_table = "boards_banner"
        verbose_name = "소개 배너"
        verbose_name_plural = "소개 배너"

    def __str__(self):
        return self.name


class Skill(models.Model):
    """배너에 표시되는 역량/스킬 칩"""
    banner = models.ForeignKey(
        Banner, on_delete=models.CASCADE, related_name="skills", verbose_name="배너",
    )
    category = models.CharField("분류", max_length=30)
    name = models.CharField("스킬명", max_length=50)
    is_main = models.BooleanField("주력 기술(강조)", default=False)
    order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        db_table = "boards_skill"
        verbose_name = "스킬"
        verbose_name_plural = "스킬 목록"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.category} - {self.name}"