from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from blog.enums import Status
from blog.models import Post, Tag

_PAGE_SIZE = 20
_PUBLISHED = Q(is_active=True, status=Status.PUBLISHED.value)


def _published_posts():
    return Post.objects.filter(_PUBLISHED).order_by("-date", "-id")


def home(request: HttpRequest) -> HttpResponse:
    page = Paginator(_published_posts(), _PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "home.html", {"page": page})


def archive(request: HttpRequest) -> HttpResponse:
    # One ordered queryset; the template regroups it by year (no extra queries).
    return render(request, "archive.html", {"posts": _published_posts()})


def tag_index(request: HttpRequest) -> HttpResponse:
    published_for_tag = Q(posts__is_active=True, posts__status=Status.PUBLISHED.value)
    tags = (
        Tag.objects.annotate(count=Count("posts", filter=published_for_tag))
        .filter(count__gt=0)
        .order_by("-count", "slug")
    )
    return render(request, "tag_index.html", {"tags": tags})


def tag_detail(request: HttpRequest, slug: str) -> HttpResponse:
    tag = get_object_or_404(Tag, slug=slug)
    posts = _published_posts().filter(tags=tag)
    page = Paginator(posts, _PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "tag_detail.html", {"tag": tag, "page": page})


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
