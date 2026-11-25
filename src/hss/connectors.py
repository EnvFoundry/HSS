"""Small, explicit clients for scholarly metadata and public indicators."""

import json
import os
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


def fetch(url, headers=None):
    request = Request(
        url,
        headers={
            "User-Agent": "EnvFoundry-HSS",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def search(provider, query="", limit=10, options=None):
    options = options or {}
    limit = max(1, min(int(limit), 100))
    if provider == "crossref":
        params = {"query.bibliographic": query, "rows": limit}
        if options.get("mailto"):
            params["mailto"] = options["mailto"]
        payload = fetch("https://api.crossref.org/works?" + urlencode(params))
        records = []
        for item in payload["message"]["items"]:
            records.append(
                {
                    "id": item.get("DOI"),
                    "doi": item.get("DOI"),
                    "title": " ".join(item.get("title", [])),
                    "authors": [
                        " ".join(filter(None, [a.get("given"), a.get("family")]))
                        for a in item.get("author", [])
                    ],
                    "year": item.get("issued", {}).get("date-parts", [[None]])[0][0],
                    "url": item.get("URL"),
                    "type": item.get("type"),
                }
            )
        return {
            "provider": provider,
            "records": records,
            "total": payload["message"].get("total-results"),
        }
    if provider == "openalex":
        params = {"search": query, "per-page": limit}
        key = os.environ.get(options.get("key_env", "OPENALEX_API_KEY"))
        if key:
            params["api_key"] = key
        payload = fetch("https://api.openalex.org/works?" + urlencode(params))
        return {
            "provider": provider,
            "records": [
                {
                    "id": w["id"],
                    "title": w.get("display_name"),
                    "doi": w.get("doi"),
                    "year": w.get("publication_year"),
                    "authors": [
                        a["author"]["display_name"] for a in w.get("authorships", [])
                    ],
                    "url": (w.get("primary_location") or {}).get("landing_page_url"),
                    "open_access": w.get("open_access"),
                }
                for w in payload["results"]
            ],
            "total": payload["meta"]["count"],
        }
    if provider == "worldbank":
        country = quote(str(options.get("country", "all")), safe=";")
        indicator = quote(str(options.get("indicator", query)), safe=".")
        if not indicator:
            raise ValueError("Provide an indicator code, such as SP.POP.TOTL")
        params = {
            "format": "json",
            "per_page": limit,
            "page": int(options.get("page", 1)),
        }
        if options.get("date"):
            params["date"] = options["date"]
        payload = fetch(
            f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?"
            + urlencode(params)
        )
        if not isinstance(payload, list) or len(payload) != 2:
            raise ValueError("The indicator service returned no data table")
        return {"provider": provider, "page": payload[0], "records": payload[1] or []}
    if provider == "zotero":
        scope = options.get("scope", "users")
        if scope not in {"users", "groups"}:
            raise ValueError("Zotero scope must be users or groups")
        library = str(options["library"])
        if not library.isdigit():
            raise ValueError("Zotero requires a numeric library ID")
        headers = {"Zotero-API-Version": "3"}
        key = os.environ.get(options.get("key_env", "ZOTERO_API_KEY"))
        if key:
            headers["Zotero-API-Key"] = key
        payload = fetch(
            f"https://api.zotero.org/{scope}/{library}/items?"
            + urlencode({"q": query, "limit": limit, "format": "json"}),
            headers,
        )
        return {
            "provider": provider,
            "records": [{"id": item["key"], **item["data"]} for item in payload],
        }
    raise ValueError(
        "No built-in client for "
        + provider
        + "; use the resource's documented service or host connector"
    )
