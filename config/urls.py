"""Root URL configuration.

The Django admin is intentionally NOT routed here: per the project constitution
it is Tailscale-gated and never exposed on public routes. It gets wired behind
the tailnet in a later node.
"""

from django.urls import path
from django.views.generic.base import RedirectView

from blog.feeds import PostFeed
from blog.views import home

urlpatterns = [
    path("", home, name="home"),
    path("feed.xml", PostFeed(), name="feed"),
    path("rss", RedirectView.as_view(url="/feed.xml", permanent=True)),
    path("atom.xml", RedirectView.as_view(url="/feed.xml", permanent=True)),
]
