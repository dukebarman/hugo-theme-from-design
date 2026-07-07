~version: "2.1"

# Reusable starting point for Hugo article themes.
# Keep ~version as the first rule in Telegram IV Editor. Do not delete it:
# Telegram needs this line to parse the template as Instant View 2.1.
# Adapt ?path to the live site's URL structure, such as /posts/, /blog/,
# /articles/, or /docs/. Telegram Instant View templates are configured and
# validated per live domain in Telegram's editor.

?path: /([a-z]{2}/)?posts/.+
!exists: //article[@data-iv-article]

$article: //article[@data-iv-article]
$body: $article//*[@data-iv-content]

@remove: $article//*[contains(@data-iv-remove, "true")]
@remove: //script
@remove: //style
@remove: //noscript

title: $article//h1[contains(concat(" ", normalize-space(@class), " "), " iv-title ")]
@datetime(0): $article//time[@data-iv-published]/@datetime
published_date: $@
author: //meta[@property="article:author"]/@content
author_url: //meta[@property="article:author:url"]/@content
author_url: //link[@rel="author"]/@href
description: //meta[@name="description"]/@content
image_url: //meta[@property="og:image"]/@content
site_name: //meta[@property="og:site_name"]/@content
cover: $article//figure[@data-iv-cover]
body: $body
