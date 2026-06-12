"""Root URL configuration.

The Django admin is intentionally NOT routed here: per the project constitution
it is Tailscale-gated and never exposed on public routes. It gets wired behind
the tailnet in a later node.
"""

from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.generic.base import RedirectView

from blog.feeds import PostFeed
from blog.sitemaps import PostSitemap, TagSitemap
from blog.views import home, post_detail, robots_txt, tag_detail, tag_index

_SITEMAPS = {"posts": PostSitemap, "tags": TagSitemap}

urlpatterns = [
    path("", home, name="home"),
    path("posts/<slug:slug>", post_detail, name="post"),
    path("tags/", tag_index, name="tags"),
    path("tags/<slug:slug>", tag_detail, name="tag"),
    path("feed.xml", PostFeed(), name="feed"),
    path("rss", RedirectView.as_view(url="/feed.xml", permanent=True)),
    path("atom.xml", RedirectView.as_view(url="/feed.xml", permanent=True)),
    path("sitemap.xml", sitemap, {"sitemaps": _SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt),
]
