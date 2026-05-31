~version: "2.1"

# Reusable starting point for Hugo article themes.
# Adapt ?path to the live site's URL structure, such as /posts/, /blog/,
# /articles/, or /docs/. Telegram Instant View templates are configured and
# validated per live domain in Telegram's editor.

?exists: //article[@data-iv-article]
?path: .*\/posts\/.+

@remove: //*[contains(@data-iv-remove, "true")]
@remove: //script
@remove: //style

title: //h1[contains(concat(" ", normalize-space(@class), " "), " iv-title ")]
published_date: //time[@data-iv-published]/@datetime
author: //meta[@property="article:author"]/@content
description: //meta[@name="description"]/@content
image_url: //meta[@property="og:image"]/@content
cover: //figure[@data-iv-cover]
body: //*[@data-iv-content]
