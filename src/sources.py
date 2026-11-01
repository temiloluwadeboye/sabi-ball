"""Which Wikipedia pages go into the corpus.

Most pages come from Wikipedia categories (every page in "Premier League seasons", and so on).
Some topics are not grouped in a category, so those pages are listed by name in EXTRA_PAGES.
"""

CATEGORIES = [
    # Top 5 leagues: seasons and current clubs
    "Premier League seasons",
    "La Liga seasons",
    "Serie A seasons",
    "Bundesliga seasons",
    "Ligue 1 seasons",
    "Premier League clubs",
    "La Liga clubs",
    "Serie A clubs",
    "Bundesliga clubs",
    "Ligue 1 clubs",
    # UEFA club competitions
    "UEFA Champions League seasons",
    "UEFA Europa League seasons",
    "UEFA Champions League finals",
    "UEFA Europa League finals",
    # International tournaments
    "FIFA World Cup tournaments",
    "FIFA World Cup finals",
    "Africa Cup of Nations tournaments",
    "UEFA European Championship tournaments",
    "Copa América tournaments",
    "UEFA Nations League",
    # Awards
    "Ballon d'Or",
]

# Olympic football has one page per Games; from 1996 there are separate men's and women's pages.
# 1932 had no football tournament. Pages that turn out not to exist are skipped by the downloader.
OLYMPIC_YEARS = [1900, 1904, 1908, 1912, 1920, 1924, 1928, 1936, 1948, 1952, 1956, 1960,
                 1964, 1968, 1972, 1976, 1980, 1984, 1988, 1992, 1996, 2000, 2004, 2008,
                 2012, 2016, 2020, 2024]

EXTRA_PAGES = [
    "Football at the Summer Olympics",
    "Kopa Trophy",
    "FIFA Puskás Award",
    "UEFA Nations League",
]
