# app/modules/data_retriever.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

import logging
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
S = get_settings()


class DataRetriever:
    """
    Executes api_intents from the context_pack and attaches
    REAL retrieved data (weather + POI knowledge).

    This is your RAG layer for external world data:
      - get_weather -> Open-Meteo (free)
      - search_pois -> Wikipedia (free)
      - search_lodging -> (simple heuristic / derived from POIs)

    Output is merged into `grounded_context["retrieved_data"]` so
    FilterEngine + LLMModule can consume it.
    """

    def __init__(self) -> None:
        logger.info("DR: DataRetriever initialized (RAG mode)")

    async def retrieve(self, context_pack: Dict[str, Any]) -> Dict[str, Any]:
        """
        Take the context_pack from ContextManager and execute its
        api_intents. Returns a new dict (grounded_context) with
        a 'retrieved_data' field attached.

        grounded_context["retrieved_data"] has shape:

        {
          "weather": { ... } | None,
          "pois":    [ {id, name, summary, url, ...}, ... ],
          "lodging": [ {...}, ... ],
        }
        """
        thread_id = context_pack.get("thread_id")
        api_intents: List[Dict[str, Any]] = context_pack.get("api_intents", [])
        cache_keys: Dict[str, str] = context_pack.get("cache_keys", {})
        geoscope: Dict[str, Any] = context_pack.get("geoscope", {}) or {}
        destination: Dict[str, Any] = geoscope.get("destination", {}) or {}
        time_block: Dict[str, Any] = context_pack.get("time", {}) or {}

        logger.info(
            "DR: start retrieval for thread_id=%s with %d api_intents",
            thread_id,
            len(api_intents),
        )

        # Try to get a human-friendly place name for POI / wiki search
        place_name = (
            destination.get("name")
            or destination.get("primary_city")
            or destination.get("region_label")
            or destination.get("region_code")
            or "California"
        )

        retrieved: Dict[str, Any] = {
            "weather": None,
            "pois": [],
            "lodging": [],
        }

        # Use a single shared HTTP client (cheap, async)
        async with httpx.AsyncClient(timeout=10.0) as client:
            for intent in api_intents:
                tool = intent.get("tool")
                params = intent.get("params", {}) or {}
                caps = intent.get("caps", {}) or {}

                logger.info(
                    "DR: executing intent tool=%s params=%s caps=%s",
                    tool,
                    params,
                    caps,
                )

                try:
                    if tool == "get_weather":
                        weather = await self._get_weather_open_meteo(
                            client=client,
                            place_name=place_name,
                            params=params,
                            time_block=time_block,
                            cache_key=cache_keys.get("weather"),
                        )
                        retrieved["weather"] = weather

                    elif tool == "search_pois":
                        pois = await self._search_pois_wikipedia(
                            client=client,
                            place_name=place_name,
                            params=params,
                            cache_key=cache_keys.get("pois"),
                        )
                        retrieved["pois"] = pois

                    elif tool == "search_lodging":
                        lodging = await self._derive_lodging_from_context(
                            place_name=place_name,
                            params=params,
                            pois=retrieved.get("pois", []),
                            cache_key=cache_keys.get("lodging"),
                        )
                        retrieved["lodging"] = lodging

                    else:
                        logger.warning("DR: unknown tool '%s' in api_intents", tool)

                except Exception:
                    # Best-effort: log and continue, don't break the whole pipeline
                    logger.exception(
                        "DR: error while executing tool=%s for thread_id=%s",
                        tool,
                        thread_id,
                    )

        logger.info(
            "DR: retrieval done for thread_id=%s -> weather=%s, pois=%d, lodging=%d",
            thread_id,
            "yes" if retrieved.get("weather") else "no",
            len(retrieved.get("pois", [])),
            len(retrieved.get("lodging", [])),
        )

        grounded_context = {
            **context_pack,
            "retrieved_data": retrieved,
        }
        return grounded_context

    # ------------------------------------------------------------------
    # WEATHER (Open-Meteo, completely free, no key)
    # ------------------------------------------------------------------

    async def _get_weather_open_meteo(
        self,
        client: httpx.AsyncClient,
        place_name: str,
        params: Dict[str, Any],
        time_block: Dict[str, Any],
        cache_key: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        RAG source 1: Open-Meteo geocoding + forecast.
        - Free, no API key
        - https://open-meteo.com/
        """

        logger.info(
            "DR: _get_weather_open_meteo place_name=%s cache_key=%s",
            place_name,
            cache_key,
        )

        # 1) Geocode the place name -> lat / lon
        try:
            geo_resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": place_name, "count": 1, "language": "en", "format": "json"},
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
            results = geo_data.get("results") or []
            if not results:
                logger.warning("DR: geocoding returned no results for %s", place_name)
                return None

            loc = results[0]
            lat = loc["latitude"]
            lon = loc["longitude"]
            resolved_name = loc.get("name") or place_name
            country = loc.get("country")
        except Exception:
            logger.exception("DR: Failed geocoding for %s", place_name)
            return None

        # 2) Forecast
        try:
            # If you want, you can use time_block["start"]/["end"] to choose forecast horizon
            forecast_resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "weathercode,temperature_2m_max,temperature_2m_min",
                    "timezone": "auto",
                },
            )
            forecast_resp.raise_for_status()
            f = forecast_resp.json()
        except Exception:
            logger.exception("DR: Failed fetching forecast from Open-Meteo")
            return None

        daily = []
        try:
            dates = f["daily"]["time"]
            max_t = f["daily"]["temperature_2m_max"]
            min_t = f["daily"]["temperature_2m_min"]
            codes = f["daily"]["weathercode"]

            for i in range(len(dates)):
                daily.append(
                    {
                        "date": dates[i],
                        "weather_code": codes[i],
                        "temp_max_c": max_t[i],
                        "temp_min_c": min_t[i],
                    }
                )
        except Exception:
            logger.exception("DR: unexpected daily forecast shape")
            daily = []

        return {
            "provider": "open-meteo",
            "resolved_place": resolved_name,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "daily": daily,
        }

    # ------------------------------------------------------------------
    # POIs / KNOWLEDGE (Wikipedia, free)
    # ------------------------------------------------------------------

    async def _search_pois_wikipedia(
        self,
        client: httpx.AsyncClient,
        place_name: str,
        params: Dict[str, Any],
        cache_key: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        RAG source 2: Wikipedia search.
        We treat Wikipedia pages as "POI knowledge chunks".

        This gives the LLM rich text about the destination that it can
        ground on when building the itinerary.
        """
        tags = params.get("tags") or []
        season_hint = params.get("season_hint") or "ANY"

        # Compose a query like "Big Sur attractions hiking camping"
        extra_terms = []
        if tags:
            extra_terms.extend(tags)
        extra_terms.append("things to do")
        query = f"{place_name} " + " ".join(extra_terms)

        logger.info(
            "DR: _search_pois_wikipedia query=%s season_hint=%s cache_key=%s",
            query,
            season_hint,
            cache_key,
        )

        # Use Wikipedia API: generator=search to get multiple pages
        # Docs: https://www.mediawiki.org/wiki/API:Search
        try:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "extracts|info",
                    "explaintext": 1,
                    "exintro": 1,
                    "inprop": "url",
                    "generator": "search",
                    "gsrsearch": query,
                    "gsrlimit": 10,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("DR: Wikipedia search failed")
            return []

        pages = (data.get("query") or {}).get("pages") or {}
        pois: List[Dict[str, Any]] = []

        for page_id, page in pages.items():
            title = page.get("title")
            extract = (page.get("extract") or "").strip()
            fullurl = page.get("fullurl")

            if not title or not extract:
                continue

            # We treat each page as a "POI/knowledge chunk"
            pois.append(
                {
                    "id": f"wiki-{page_id}",
                    "name": title,
                    "summary": extract[:1200],  # keep first ~1200 chars
                    "url": fullurl,
                    "source": "wikipedia",
                    "region_hint": place_name,
                    "season_hint": season_hint,
                    "tags": tags,
                }
            )

        logger.info(
            "DR: wikipedia: got %d POI knowledge chunks for place=%s",
            len(pois),
            place_name,
        )
        return pois

    # ------------------------------------------------------------------
    # LODGING (cheap heuristic / can replace later with real API)
    # ------------------------------------------------------------------

    async def _derive_lodging_from_context(
        self,
        place_name: str,
        params: Dict[str, Any],
        pois: List[Dict[str, Any]],
        cache_key: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        For now, we synthesize lodging options instead of calling a paid API.
        This is still RAG-ish because LLM will get structured candidates
        it can reason over.

        Later you can swap this out with OpenStreetMap / OpenTripMap
        (both have free tiers / open data).
        """
        lodging_type = params.get("type") or "CAMPING"
        pet_friendly = params.get("pet_friendly", False)

        logger.info(
            "DR: _derive_lodging_from_context place_name=%s type=%s pet_friendly=%s cache_key=%s",
            place_name,
            lodging_type,
            pet_friendly,
            cache_key,
        )

        # Basic heuristic examples; in real v1 you’d replace with real POI → lodging search
        base_lodging = [
            {
                "id": "lodging-1",
                "name": f"{place_name} Riverside {lodging_type.title()} Spot",
                "type": lodging_type,
                "pet_friendly": True,
                "approx_price_per_night_usd": 70 if lodging_type == "CAMPING" else 220,
                "description": f"Simple, scenic {lodging_type.lower()} option near key attractions in {place_name}.",
            },
            {
                "id": "lodging-2",
                "name": f"{place_name} Viewpoint {lodging_type.title()}",
                "type": lodging_type,
                "pet_friendly": False,
                "approx_price_per_night_usd": 50 if lodging_type == "CAMPING" else 180,
                "description": f"Budget-friendly {lodging_type.lower()} with quick access to popular viewpoints.",
            },
        ]

        if pet_friendly:
            pf = [l for l in base_lodging if l.get("pet_friendly")]
            return pf or base_lodging

        return base_lodging
