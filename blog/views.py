from django.http import HttpRequest, HttpResponse


def home(request: HttpRequest) -> HttpResponse:
    return HttpResponse("blog — coming soon\n", content_type="text/plain; charset=utf-8")
