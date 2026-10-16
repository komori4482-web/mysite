import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import Profile

from .models import Comment, Post, PostFile
from .validators import MAX_FILE_SIZE, MAX_FILES_PER_POST

User = get_user_model()
PW = "Str0ng-Pass-2026!"
TMP_MEDIA = tempfile.mkdtemp(prefix="test_media_")


def make_user(email, nickname):
    u = User.objects.create_user(email=email, password=PW)
    Profile.objects.create(user=u, nickname=nickname)
    return u


def png(name="a.png"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class BoardBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.alice = make_user("alice@example.com", "alice")
        self.bob = make_user("bob@example.com", "bob")
        self.post = Post.objects.create(author=self.alice, title="hello", content="body")
        self.comment = Comment.objects.create(post=self.post, author=self.alice, content="c1")

    def login(self, user):
        self.client.force_login(user)


class PostPermissionTests(BoardBase):
    def test_public_pages_are_open(self):
        self.assertEqual(self.client.get(reverse("boards:post_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("boards:post_detail", args=[self.post.pk])).status_code, 200)

    def test_anonymous_is_sent_to_login(self):
        targets = [
            ("get", reverse("boards:post_create")),
            ("get", reverse("boards:post_update", args=[self.post.pk])),
            ("get", reverse("boards:post_delete", args=[self.post.pk])),
            ("post", reverse("boards:comment_create", args=[self.post.pk])),
            ("get", reverse("boards:comment_update", args=[self.comment.pk])),
            ("post", reverse("boards:comment_delete", args=[self.comment.pk])),
        ]
        for method, url in targets:
            r = getattr(self.client, method)(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse("accounts:login"), r["Location"], url)

    def test_non_author_cannot_edit_or_delete_post(self):
        self.login(self.bob)
        for url in (
            reverse("boards:post_update", args=[self.post.pk]),
            reverse("boards:post_delete", args=[self.post.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 403, url)
            self.assertEqual(self.client.post(url, {"title": "hacked", "content": "x"}).status_code, 403, url)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "hello")

    def test_author_can_edit_and_delete_post(self):
        self.login(self.alice)
        r = self.client.post(
            reverse("boards:post_update", args=[self.post.pk]),
            {"title": "edited", "content": "new body"},
        )
        self.assertEqual(r.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "edited")

        self.client.post(reverse("boards:post_delete", args=[self.post.pk]))
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_create_sets_author_from_session_not_form(self):
        self.login(self.bob)
        self.client.post(
            reverse("boards:post_create"),
            {"title": "mine", "content": "x", "author": self.alice.pk},
        )
        self.assertEqual(Post.objects.get(title="mine").author, self.bob)

    def test_pagination_is_nine_per_page(self):
        Post.objects.bulk_create(
            [Post(author=self.alice, title=f"p{i}", content="x") for i in range(12)]
        )  # + setUp 의 1개 = 13개
        r = self.client.get(reverse("boards:post_list"))
        self.assertEqual(len(r.context["posts"]), 9)
        r = self.client.get(reverse("boards:post_list") + "?page=2")
        self.assertEqual(len(r.context["posts"]), 4)


class CommentPermissionTests(BoardBase):
    def test_comment_create_and_reply(self):
        self.login(self.bob)
        url = reverse("boards:comment_create", args=[self.post.pk])
        self.client.post(url, {"content": "hi"})
        self.client.post(url, {"content": "reply", "parent": self.comment.pk})
        reply = Comment.objects.get(content="reply")
        self.assertEqual(reply.parent, self.comment)
        self.assertEqual(reply.author, self.bob)

    def test_cannot_reply_to_a_reply_or_other_posts_comment(self):
        reply = Comment.objects.create(post=self.post, author=self.bob, content="r", parent=self.comment)
        other = Post.objects.create(author=self.alice, title="other", content="x")
        self.login(self.bob)
        url = reverse("boards:comment_create", args=[self.post.pk])
        self.assertEqual(self.client.post(url, {"content": "x", "parent": reply.pk}).status_code, 404)
        url2 = reverse("boards:comment_create", args=[other.pk])
        self.assertEqual(self.client.post(url2, {"content": "x", "parent": self.comment.pk}).status_code, 404)

    def test_non_author_cannot_edit_or_delete_comment(self):
        self.login(self.bob)
        up = reverse("boards:comment_update", args=[self.comment.pk])
        de = reverse("boards:comment_delete", args=[self.comment.pk])
        self.assertEqual(self.client.get(up).status_code, 403)
        self.assertEqual(self.client.post(up, {"content": "hacked"}).status_code, 403)
        self.assertEqual(self.client.post(de).status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "c1")

    def test_comment_delete_requires_post(self):
        self.login(self.alice)
        de = reverse("boards:comment_delete", args=[self.comment.pk])
        self.assertEqual(self.client.get(de).status_code, 405)
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())
        self.client.post(de)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_deleting_parent_removes_replies(self):
        Comment.objects.create(post=self.post, author=self.bob, content="r", parent=self.comment)
        self.login(self.alice)
        self.client.post(reverse("boards:comment_delete", args=[self.comment.pk]))
        self.assertEqual(Comment.objects.count(), 0)


class UploadValidationTests(BoardBase):
    def post_with(self, *files, user=None, url=None):
        self.login(user or self.alice)
        return self.client.post(
            url or reverse("boards:post_create"),
            {"title": "t", "content": "c", "files": list(files)},
        )

    def test_valid_image_and_document(self):
        pdf = SimpleUploadedFile("doc.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = self.post_with(png(), pdf)
        self.assertEqual(r.status_code, 302)
        files = {f.original_name: f.is_image for f in PostFile.objects.filter(post__title="t")}
        self.assertEqual(files, {"a.png": True, "doc.pdf": False})

    def test_dangerous_extensions_rejected(self):
        for name in ("evil.html", "evil.svg", "evil.js", "evil.exe", "evil.php", "noext"):
            f = SimpleUploadedFile(name, b"<script>alert(1)</script>", content_type="image/png")
            r = self.post_with(f)
            self.assertEqual(r.status_code, 200, name)  # 저장 안 되고 폼 재표시
            self.assertEqual(PostFile.objects.count(), 0, name)
            self.assertFalse(Post.objects.filter(title="t").exists(), name)

    def test_fake_image_rejected_even_with_image_extension(self):
        fake = SimpleUploadedFile("fake.png", b"this is not an image", content_type="image/png")
        r = self.post_with(fake)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PostFile.objects.count(), 0)

    def test_oversize_rejected(self):
        big = SimpleUploadedFile("big.pdf", b"0" * (MAX_FILE_SIZE + 1), content_type="application/pdf")
        r = self.post_with(big)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PostFile.objects.count(), 0)

    def test_file_count_limit(self):
        files = [png(f"{i}.png") for i in range(MAX_FILES_PER_POST + 1)]
        r = self.post_with(*files)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PostFile.objects.count(), 0)

    def test_count_limit_includes_existing_files_on_update(self):
        for i in range(MAX_FILES_PER_POST):
            PostFile.objects.create(post=self.post, file=f"x{i}.png", original_name=f"x{i}.png", is_image=True)
        r = self.post_with(png("one-more.png"), url=reverse("boards:post_update", args=[self.post.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.post.files.count(), MAX_FILES_PER_POST)

    def test_update_can_add_files(self):
        r = self.post_with(png("added.png"), url=reverse("boards:post_update", args=[self.post.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.post.files.count(), 1)


class VideoUrlTests(BoardBase):
    def test_supported_and_unsupported_urls(self):
        self.login(self.alice)
        url = reverse("boards:post_create")
        ok = self.client.post(url, {"title": "v", "content": "c", "video_url": "https://youtu.be/dQw4w9WgXcQ"})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(Post.objects.get(title="v").video_embed[0], "iframe")

        bad = self.client.post(url, {"title": "v2", "content": "c", "video_url": "https://evil.example/x"})
        self.assertEqual(bad.status_code, 200)
        self.assertFalse(Post.objects.filter(title="v2").exists())

    def test_youtube_lookalike_host_is_not_embedded(self):
        p = Post(video_url="https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ")
        self.assertIsNone(p.video_embed)


class BoardCsrfTests(BoardBase):
    def test_post_without_csrf_token_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        r = client.post(reverse("boards:post_delete", args=[self.post.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())