from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from blog.enums import Status
from blog.models import Post

_PAGE_SIZE = 20


def home(request: HttpRequest) -> HttpResponse:
    posts = Post.objects.filter(is_active=True, status=Status.PUBLISHED.value).order_by(
        "-date", "-id"
    )
    page = Paginator(posts, _PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "home.html", {"page": page})


def post_detail(request: HttpRequest, slug: str) -> HttpResponse:
    post = get_object_or_404(Post, slug=slug, is_active=True, status=Status.PUBLISHED.value)
    return render(request, "post_detail.html", {"post": post})


def robots_txt(request: HttpRequest) -> HttpResponse:
    if settings.IS_PREVIEW:
        body = "User-agent: *\nDisallow: /\n"
    else:
        lines: list[str] = []
        for bot in settings.BLOCKED_BOTS:
            lines += [f"User-agent: {bot}", "Disallow: /", ""]
        lines += ["User-agent: *", "Disallow:", ""]
        lines.append(f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml")
        body = "\n".join(lines) + "\n"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")
