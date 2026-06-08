"""Root URL configuration.

The Django admin is intentionally NOT routed here: per the project constitution
it is Tailscale-gated and never exposed on public routes. It gets wired behind
the tailnet in a later node.
"""

from django.urls import path

from blog.views import home

urlpatterns = [
    path("", home, name="home"),
]
