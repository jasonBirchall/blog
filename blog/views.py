from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from blog.enums import Status
from blog.models import Post


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


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
