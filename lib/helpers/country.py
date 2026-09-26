import asyncio

import pycountry
from pycountry.db import Country
from rapidfuzz import fuzz, process


async def fuzzy_search_country(search: str, cutoff: int = 65) -> list[Country]:
    countries: list[Country] = []

    try:
        countries.extend(await asyncio.to_thread(pycountry.countries.search_fuzzy, search))
    except LookupError:
        pass

    country_fuzz = await asyncio.to_thread(
        process.extract,
        search,
        list(pycountry.countries),
        scorer=fuzz.WRatio,
        limit=25,
        score_cutoff=cutoff,
        processor=lambda country: country.name if isinstance(country, Country) else country,
    )
    countries.extend([c[0] for c in country_fuzz])

    return list(set(countries))
