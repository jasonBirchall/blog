"""Root URL configuration.

The Django admin is intentionally NOT routed here: per the project constitution
it is Tailscale-gated and never exposed on public routes. It gets wired behind
the tailnet in a later node.
"""

from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.generic.base import RedirectView

from blog.feeds import PostFeed
from blog.sitemaps import PostSitemap, StaticSitemap, TagSitemap
from blog.views import (
    about,
    archive,
    home,
    now,
    post_detail,
    robots_txt,
    search,
    tag_detail,
    tag_index,
)

_SITEMAPS = {"posts": PostSitemap, "tags": TagSitemap, "static": StaticSitemap}

urlpatterns = [
    path("", home, name="home"),
    path("about", about, name="about"),
    path("now", now, name="now"),
    # Reserved slugs: wikilinks resolve [[now]]/[[about]] to /posts/<slug>;
    # redirect each to its top-level page. Must precede the generic slug pattern
    # to win the match. (The /about view lands in A.2; the redirect stands alone.)
    path("posts/now", RedirectView.as_view(url="/now", permanent=True)),
    path("posts/about", RedirectView.as_view(url="/about", permanent=True)),
    path("posts/<slug:slug>", post_detail, name="post"),
    path("tags/", tag_index, name="tags"),
    path("tags/<slug:slug>", tag_detail, name="tag"),
    path("archive/", archive, name="archive"),
    path("search", search, name="search"),
    path("feed.xml", PostFeed(), name="feed"),
    path("rss", RedirectView.as_view(url="/feed.xml", permanent=True)),
    path("atom.xml", RedirectView.as_view(url="/feed.xml", permanent=True)),
    path("sitemap.xml", sitemap, {"sitemaps": _SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt),
]
