"""All post formats. Each has: renderer, what the AI must write (fields), and an idea hint."""

FORMATS = {
    "meme_card": {
        "renderer": "meme", "kind": "image",
        "hint": "Classic desi meme: setup line on top, punchline at bottom, one big food emoji in the middle.",
        "fields": {"top": "setup line (max 12 words)", "bottom": "punchline (max 10 words)",
                   "item": "one menu item name shown in the middle"},
    },
    "relatable_exam": {
        "renderer": "meme", "kind": "image",
        "hint": "IIT life pain: end-sems, quizzes, assignments, placements, internships, attendance, profs' surprise tests — cafe as the escape.",
        "fields": {"top": "setup", "bottom": "punchline", "item": "menu item"},
    },
    "local_roorkee": {
        "renderer": "meme", "kind": "image",
        "hint": "Roorkee local humour: Ganga canal walks, Roorkee ki thand, Civil Lines, Haridwar/Dehradun trips, Delhi wale dost, bus/train back home, power cuts, monsoon.",
        "fields": {"top": "setup", "bottom": "punchline", "item": "menu item"},
    },
    "trend_twist": {
        "renderer": "meme", "kind": "image",
        "hint": "Take the CURRENT TREND given below and make a Bhavya Cafe version of that exact meme format/dialogue.",
        "fields": {"top": "setup in the trend's format", "bottom": "punchline", "item": "menu item"},
        "needs_trend": True,
    },
    "versus": {
        "renderer": "versus", "kind": "image",
        "hint": "Expectation vs reality / Mess vs Bhavya / Hostel maggi vs Bhavya — left side sad, right side happy (Bhavya).",
        "fields": {"headline": "short headline", "left_title": "left label (sad)", "left_line": "one line",
                   "left_emoji": "single emoji", "right_title": "right label (Bhavya)", "right_line": "one line",
                   "right_item": "menu item"},
    },
    "comment_battle": {
        "renderer": "battle", "kind": "image",
        "hint": "Food fight: two menu items battle, people must COMMENT their pick. Add a funny line for each side.",
        "fields": {"question": "battle question", "a_item": "menu item A", "a_line": "funny line for A",
                   "b_item": "menu item B", "b_line": "funny line for B"},
    },
    "tag_friend": {
        "renderer": "tag", "kind": "image",
        "hint": "'Tag that friend who...' — a very specific relatable friend type from hostel/college life.",
        "fields": {"line": "the 'who...' part (max 14 words)", "item": "menu item"},
    },
    "rate_combo": {
        "renderer": "rate", "kind": "image",
        "hint": "A funny named combo of 2-3 menu items for a specific situation (e.g. 'Post-viva recovery kit'). Ask to rate 1-10 in comments.",
        "fields": {"combo_name": "funny combo name", "items": "list of 2-3 menu item names", "line": "short line"},
    },
    "weekend_plan": {
        "renderer": "checklist", "kind": "image",
        "hint": "A funny weekend/holiday plan checklist where Bhavya is the only thing that actually gets done.",
        "fields": {"headline": "title", "checklist": "list of 4 items, last one is Bhavya", "done": "list of booleans, same length"},
    },
    "spot_difference": {
        "renderer": "spotdiff", "kind": "image",
        "hint": "Interactive puzzle (generated automatically). Write a fun headline + caption pushing people to zoom and comment the answer.",
        "fields": {"headline": "short headline"},
    },
    "hidden_item": {
        "renderer": "hidden", "kind": "image",
        "hint": "Interactive puzzle: find the one odd item in a grid (generated automatically). Write a challenge headline.",
        "fields": {"headline": "short challenge headline"},
    },
    "count_items": {
        "renderer": "count", "kind": "image",
        "hint": "Interactive puzzle: count the momos in a messy table (generated automatically). Write a challenge headline.",
        "fields": {"headline": "short challenge headline"},
    },
    "zoom_read": {
        "renderer": "zoomread", "kind": "image",
        "hint": "A tiny hidden funny message inside a pattern; people must zoom/hold to read it. Give the hidden message.",
        "fields": {"headline": "short headline", "hidden_message": "funny hidden line (max 9 words)"},
    },
    "swipe_twist": {
        "renderer": "carousel", "kind": "carousel",
        "hint": "4-slide story carousel with a twist on the last slide (the twist lands on Bhavya Cafe). Build suspense so people swipe till the end.",
        "fields": {"slides": "list of 4 objects {big: max 8 words, small: max 12 words}"},
    },
    "this_or_that": {
        "renderer": "thisorthat", "kind": "carousel",
        "hint": "3-slide 'This or That' — each slide 2 options (college life or food). Comment your picks like 'A B A'.",
        "fields": {"pairs": "list of 3 objects {a: option A (max 4 words), a_emoji, b: option B, b_emoji}"},
    },
}

REEL_FORMATS = {
    "reel_meme": {
        "renderer": "reel_meme", "kind": "reel",
        "hint": "Short meme REEL (8 sec): a relatable setup line appears, then the punchline pops while the food photo zooms in. Desi IIT/Roorkee humour.",
        "fields": {"hook": "setup line (max 12 words)", "punchline": "punchline (max 10 words)", "item": "menu item"},
    },
    "reel_pov": {
        "renderer": "reel_pov", "kind": "reel",
        "hint": "'POV:' REEL — 3 short lines appear one by one telling a tiny relatable story (hostel/exam/Roorkee life) that ends at Bhavya with the item.",
        "fields": {"pov_lines": "list of exactly 3 short lines (max 9 words each), last one lands on Bhavya", "item": "menu item"},
    },
    "reel_top5": {
        "renderer": "reel_top5", "kind": "reel",
        "hint": "Countdown REEL: Top 5 menu items for a specific situation (e.g. 'Top 5 for end-sem nights', 'Top 5 under ₹70'). Items shown #5 to #1 with real prices.",
        "fields": {"title": "countdown title (max 8 words)", "items": "list of exactly 5 menu item names, #5 first, #1 last"},
    },
    "reel_this_or_that": {
        "renderer": "reel_this_or_that", "kind": "reel",
        "hint": "Fast 'This or That' REEL: 3 rounds, 3 seconds each, viewers comment their answers like 'A B A'. Mix college life and food.",
        "fields": {"pairs": "list of 3 objects {a: option A (max 4 words), a_emoji, b: option B, b_emoji}"},
    },
    "reel_pause_game": {
        "renderer": "reel_pause_game", "kind": "reel",
        "hint": "Fun PAUSE GAME reel (not an offer): menu items flash fast — 'jo item pe pause hua, wahi aaj ka dinner'. People comment what they got.",
        "fields": {"headline": "short game line (max 8 words)"},
    },
    "reel_showcase": {
        "renderer": "reel_showcase", "kind": "reel", "cat": "product",
        "hint": ("Cinematic, premium PRODUCT reel: 3 menu items, slow zoom, elegant sensory one-liners (texture, aroma, warmth) — "
                 "like a high-end cafe ad. No jokes. Make people crave it."),
        "fields": {"opening_line": "elegant opening line (max 7 words)",
                   "shots": "list of exactly 3 objects {item: exact menu item, line: sensory line max 8 words}",
                   "closing_line": "elegant closing line (max 7 words)"},
    },
    "reel_freestyle": {
        "renderer": "reel_freestyle", "kind": "reel",
        "hint": ("UNLIMITED NEW REEL: invent a FRESH reel concept every time (never repeat): e.g. 'Things only IIT Roorkee "
                 "students understand', 'Roorkee weather report but it's food', 'Exam survival guide', 'Myth vs Fact', "
                 "'Red flags in a hostel friend', 'Rating hostel excuses', 'How to impress your crush (cafe edition)', "
                 "'Types of people at Bhavya', 'Budget breakdown at month end', a mini story, a quiz... "
                 "Write 3-6 short scenes; each scene = one punchy on-screen line."),
        "fields": {"concept_title": "reel title shown first (max 8 words)",
                   "scenes": ("list of 3-6 objects {text: on-screen line max 12 words, "
                              "style: one of hook|list|question|punch|reveal, item: OPTIONAL exact menu item name or empty, "
                              "emoji: OPTIONAL one emoji or empty}"),
                   "numbered": "true if scenes are a numbered list, else false",
                   "end_line": "last screen call-to-action (max 7 words)"},
    },
}

PREMIUM_IMAGE_FORMATS = {
    "product_spotlight": {
        "renderer": "spotlight", "kind": "image", "cat": "product",
        "hint": "Premium hero poster of ONE menu item: elegant name, one sensory tagline, price. Aesthetic, no jokes.",
        "fields": {"item": "exact menu item", "tagline": "sensory tagline (max 9 words)", "kicker": "small label above name, e.g. 'Chef's pick' / 'Winter special' (max 3 words)"},
    },
    "mood_quote": {
        "renderer": "moodquote", "kind": "image", "cat": "product",
        "hint": "Aesthetic mood post: a short warm/witty line about cafe moments (slow evenings, chai conversations, rain, winter) + one item. Calm, premium.",
        "fields": {"quote": "the line (max 14 words)", "item": "exact menu item"},
    },
    "fact_carousel": {
        "renderer": "carousel", "kind": "carousel", "cat": "product",
        "hint": ("'Did you know' carousel (4 slides) about the food culture behind a menu item (e.g. history of kulhad chai, "
                 "vada pav's Mumbai story, momos' Himalayan roots). ONLY widely-known facts; no numbers you are unsure of; "
                 "never claim things about Bhavya's own recipes/sourcing. Last slide: try it at Bhavya."),
        "fields": {"slides": "list of 4 objects {big: max 8 words, small: max 16 words}"},
    },
}
FORMATS.update(PREMIUM_IMAGE_FORMATS)

OFFER_FORMATS = {
    "offer_flash_reel": {
        "renderer": "flashreel", "kind": "reel",
        "hint": "Weekly offer reel: items flash fast; whatever item is on screen when you PAUSE is FREE. Write a hype caption.",
        "fields": {"headline": "short hype line"},
    },
    "offer_zoom_code": {
        "renderer": "zoomcode", "kind": "image",
        "hint": "Weekly offer: a hidden code is inside the image; zoom, find the code, show it at the counter for a FREE item.",
        "fields": {"headline": "short hype line"},
    },
}

FORMATS.update(REEL_FORMATS)  # reels bhi normal rotation ka hissa hain
for _k, _c in {'meme_card': 'humor', 'relatable_exam': 'humor', 'local_roorkee': 'humor', 'trend_twist': 'humor', 'versus': 'humor', 'tag_friend': 'humor', 'weekend_plan': 'humor', 'comment_battle': 'interactive', 'rate_combo': 'interactive', 'spot_difference': 'interactive', 'hidden_item': 'interactive', 'count_items': 'interactive', 'zoom_read': 'interactive', 'swipe_twist': 'story', 'this_or_that': 'interactive', 'reel_meme': 'humor', 'reel_pov': 'humor', 'reel_top5': 'product', 'reel_this_or_that': 'humor', 'reel_pause_game': 'humor', 'reel_freestyle': 'story'}.items():
    FORMATS[_k].setdefault("cat", _c)
ALL_FORMATS = {**FORMATS, **OFFER_FORMATS}
