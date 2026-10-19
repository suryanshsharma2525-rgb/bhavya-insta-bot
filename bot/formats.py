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

ALL_FORMATS = {**FORMATS, **OFFER_FORMATS}
