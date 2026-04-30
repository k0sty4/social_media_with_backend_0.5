"""English-only content pool used to seed posts.

JSONPlaceholder ships Lorem Ipsum (Latin), so we generate posts locally from
these curated English snippets to guarantee the feed is in English.
"""

import random

POST_TITLES = [
    "Why small habits beat grand plans",
    "A quick note on clean code",
    "Things I learned shipping my first app",
    "Refactoring without breaking everything",
    "Reading more books in a busy week",
    "The art of a calm morning routine",
    "Five keyboard shortcuts I use every day",
    "How I stay focused on long tasks",
    "A weekend project that actually worked",
    "Notes from a long walk",
    "Minimalism for cluttered desks",
    "Saying no without feeling guilty",
    "When to rewrite and when to patch",
    "Tiny wins that change the whole day",
    "Questions I wish I asked earlier",
    "Coffee, code, and quiet hours",
    "Picking the right tool for the job",
    "Learning in public is underrated",
    "The joy of finishing something small",
    "Understanding users better than yourself",
]

POST_BODIES = [
    "I used to chase big breakthroughs, but lately the small, steady improvements are what actually move the needle. A ten-minute habit done daily beats a marathon session once a month.",
    "Clean code is mostly about kindness: to teammates, to future you, and to the poor soul debugging at 2 a.m. Clear names and small functions almost always win.",
    "Shipping is a skill on its own. You learn more from one deployed feature than from three perfect prototypes that never leave your laptop.",
    "Refactoring works best in small bites. Touch one module, run the tests, commit. Repeat. Big-bang rewrites are exciting for a week and painful for a year.",
    "Focus is a muscle. Short breaks, a clear goal, and a closed browser tab do more for productivity than any fancy app I have tried.",
    "Writing things down changes how I think. Even a messy note is better than a perfect idea I will forget by lunch.",
    "Good tools disappear into the work. If I notice my editor, something is wrong. If I notice the problem, everything is right.",
    "Most questions sound dumb in your head and obvious once answered. Ask early, save hours later.",
    "Finishing feels better than starting. It is tempting to keep polishing, but a shipped imperfect thing teaches more than a perfect unfinished one.",
    "Users surprise me every week. They use the app in ways I never planned, and those accidents usually point to the real feature I should have built.",
    "A calm morning routine is a quiet act of rebellion against a noisy world. Ten minutes of silence before email changes the rest of the day.",
    "Saying no is a design decision. Every yes adds weight, every no keeps the product sharp. I try to default to no and say yes on purpose.",
    "The best weekend projects are the ones you can finish before Sunday night. Scope down, ship fast, iterate later.",
]


def random_title() -> str:
    """Pick a random English title from the pool."""
    return random.choice(POST_TITLES)


def random_body() -> str:
    """Compose a short English body by joining one or two random snippets.

    Picking a second snippet and concatenating only when it differs keeps
    short posts possible while still producing some longer variety, so
    the feed doesn't feel repetitive.
    """
    body = random.choice(POST_BODIES)
    extra = random.choice(POST_BODIES)
    return body if extra == body else f"{body} {extra}"
