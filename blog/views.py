from django.conf import settings
from django.http import HttpRequest, HttpResponse


def home(request: HttpRequest) -> HttpResponse:
    return HttpResponse("blog — coming soon\n", content_type="text/plain; charset=utf-8")


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
