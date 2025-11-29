# app/modules/llm_module.py

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging
import os
import json
import asyncio
from app.models.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

prompt_manager = PromptManager()


try:
    import google.generativeai as genai  # type: ignore
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False
    genai = None  # type: ignore


class LLMModule:
    """
    Trip-planning LLM module.

    - If GEMINI_API_KEY is present and google-generativeai is installed,
      uses Gemini (JSON-mode) to generate a `trip_plan`.
    - Otherwise falls back to the local rule-based planner.

    The JSON shape is:

      {
        "type": "trip_plan",
        "version": "v1",
        "thread_id": "...",
        "message_id": "...",
        "destination": "human readable place",
        "days": 5,
        "trip_types": ["CAMPING", "CITY"],
        "difficulty": "EASY",
        "budget_band": "USD_0_500",
        "lodging": {
          "name": "...",
          "type": "CAMPING" | "HOTEL" | ...,
          "location": "human readable",
          "notes": "short description, human language"
        } | null,
        "weather_hint": "short plain-text summary" | null,
        "window_summary": "short plain-text recap" | null,
        "itinerary": [
          {
            "day": 1,
            "title": "Day 1 in Big Sur – Arrival and Coastal Views",
            "highlights": [
              "Sunset at Pfeiffer Beach",
              "Scenic pullouts along Highway 1"
            ],
            "activities": [
              {
                "name": "Drive the Big Sur coastline",
                "description": "Explain in 1–3 sentences in normal human language.",
                "tags": ["DRIVE", "SCENIC"],
                "estimated_time_hours": 3.5
              },
              ...
            ]
          },
          ...
        ]
      }

    All text fields should be written in natural, human-friendly sentences
    (no markdown tables or numbered list formatting inside the strings).
    """

    def __init__(self) -> None:
        self.use_gemini = False
        self._gemini_model = None

        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL_NAME", "models/gemini-flash-latest")

        if api_key and _HAS_GEMINI:
            try:
                genai.configure(api_key=api_key)
                # We keep the system instructions here so every call shares them
                self._gemini_model = genai.GenerativeModel(
                    model_name,
                   system_instruction=(
    "You are TravelBot, an expert travel itinerary planner and friendly chat assistant. "
    "You ALWAYS respond with a single valid JSON object. "
    "Inside the JSON values, use conversational, natural language as if talking directly to the traveler. "
    "For summaries, day titles, activity descriptions, and weather hints, write in complete sentences, not lists or fragments."
),
                )
                self.use_gemini = True
                logger.info(
                    "LLMModule initialized with Gemini model=%s", model_name
                )
            except Exception as e:
                logger.exception(
                    "Failed to initialize Gemini, falling back to rule-based planner: %s",
                    e,
                )
        else:
            if not api_key:
                logger.warning(
                    "GEMINI_API_KEY not set – LLMModule in RULE-BASED mode."
                )
            elif not _HAS_GEMINI:
                logger.warning(
                    "google-generativeai not installed – LLMModule in RULE-BASED mode."
                )

        if not self.use_gemini:
            logger.info("LLMModule initialized in RULE-BASED mode (no external LLM).")

    # ------------------------------------------------------------------ public API

    async def generate_plan(
        self,
        grounded_context: Dict[str, Any],
        context_pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Main entrypoint used by TripOrchestrator.

        Tries Gemini first (if available), otherwise falls back to
        the local rule-based planner.
        """
        if self.use_gemini and self._gemini_model is not None:
            try:
                logger.info("LLMModule.generate_plan: using Gemini")
                return await self._call_gemini(grounded_context, context_pack)
            except Exception as e:
                logger.exception(
                    "Gemini call failed, falling back to rule-based planner: %s", e
                )

        logger.info("LLMModule.generate_plan: using RULE-BASED planner")
        return self._rule_based_plan(grounded_context, context_pack)

    # ------------------------------------------------------------------ Gemini path

    async def _call_gemini(
        self,
        grounded_context: Dict[str, Any],
        context_pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call Gemini in JSON mode to get a structured, but human-readable, trip_plan.
        """

        if self._gemini_model is None:
            raise RuntimeError("Gemini model not initialized")

        # Compact inputs for the LLM
        thread_id = context_pack.get("thread_id")
        msg_id = context_pack.get("message_id")
        destination_obj = (context_pack.get("geoscope") or {}).get("destination") or {}
        destination_name = (
            destination_obj.get("display_name")
            or destination_obj.get("name")
            or destination_obj.get("region_code")
            or "your destination"
        )

        # small, focused JSON blobs for the LLM
        llm_input = {
            "context_pack": {
                "thread_id": thread_id,
                "message_id": msg_id,
                "window_summary": context_pack.get("window_summary"),
                "constraints": context_pack.get("constraints"),
                "geoscope": context_pack.get("geoscope"),
                "time": context_pack.get("time"),
            },
            "grounded_context": {
                "pois": grounded_context.get("pois", []),
                "lodging": grounded_context.get("lodging", []),
                "weather": grounded_context.get("weather", {}),
            },
        }

        base_prompt = await prompt_manager.get_prompt()
        user_prompt = base_prompt + json.dumps(llm_input, ensure_ascii=False)

        print('LLM INPUT' , llm_input)

        # google-generativeai is sync; run in a thread so our API stays async
        def _run_sync_call() -> Dict[str, Any]:
            response = self._gemini_model.generate_content(
                [user_prompt],
                generation_config={
                    # ask Gemini to return JSON only
                    "response_mime_type": "application/json",
                    "temperature": 0.4,
                },
            )

            # In JSON mode, response.text should already be pure JSON
            raw = getattr(response, "text", None)
            if not raw:
                # safety: try to dig into parts if text is empty
                try:
                    parts = response.candidates[0].content.parts
                    raw = "".join(p.text for p in parts if hasattr(p, "text"))
                except Exception:
                    raise RuntimeError("Gemini response had no text content")

            try:
                parsed = json.loads(raw)
                print("llm response", response)

                trip_plan: Dict[str, Any]

                # Case 1: wrapper object { "reply": { ...trip_plan... } }
                if isinstance(parsed, dict) and "reply" in parsed:
                    trip_plan = parsed["reply"]

                # Case 2: bare trip_plan object { "type": "trip_plan", ... }
                elif isinstance(parsed, dict) and parsed.get("type") == "trip_plan":
                    trip_plan = parsed

                else:
                    raise RuntimeError(
                        "LLM response did not contain a valid trip_plan "
                        "(no 'reply' and no top-level type=='trip_plan')"
                    )

            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Failed to parse Gemini JSON: {e} | raw={raw[:400]}"
                )

            # Ensure required top-level fields exist; fill from context if missing
            trip_plan.setdefault("type", "trip_plan")
            trip_plan.setdefault("version", "v1")
            trip_plan.setdefault("thread_id", thread_id)
            trip_plan.setdefault("message_id", msg_id)
            trip_plan.setdefault("destination", destination_name)

            return trip_plan

        # actually run the sync call in a thread
        trip_plan = await asyncio.to_thread(_run_sync_call)

        logger.info("LLMModule._call_gemini: received trip_plan from Gemini")
        return trip_plan


    # async def _call_gemini(
    #     self,
    #     grounded_context: Dict[str, Any],
    #     context_pack: Dict[str, Any],
    # ) -> Dict[str, Any]:
    #     """
    #     Call Gemini in JSON mode to get a structured, but human-readable, trip_plan.
    #     """

    #     if self._gemini_model is None:
    #         raise RuntimeError("Gemini model not initialized")

    #     # Compact inputs for the LLM
    #     thread_id = context_pack.get("thread_id")
    #     msg_id = context_pack.get("message_id")
    #     destination_obj = (context_pack.get("geoscope") or {}).get("destination") or {}
    #     destination_name = (
    #         destination_obj.get("display_name")
    #         or destination_obj.get("name")
    #         or destination_obj.get("region_code")
    #         or "your destination"
    #     )

    #     # small, focused JSON blobs for the LLM
    #     llm_input = {
    #         "context_pack": {
    #             "thread_id": thread_id,
    #             "message_id": msg_id,
    #             "window_summary": context_pack.get("window_summary"),
    #             "constraints": context_pack.get("constraints"),
    #             "geoscope": context_pack.get("geoscope"),
    #             "time": context_pack.get("time"),
    #         },
    #         "grounded_context": {
    #             "pois": grounded_context.get("pois", []),
    #             "lodging": grounded_context.get("lodging", []),
    #             "weather": grounded_context.get("weather", {}),
    #         },
    #     }

#         # Instructions to Gemini – schema + style, but NOT "tabular"
#                 # Instructions to Gemini – schema + style, but NOT "tabular"
#         user_prompt = (
#              """
#        You are CALI-TRIP-PRO, an expert California-only travel planner.

# ========================
# P E R S O N A
# ========================
# - You are a friendly, enthusiastic, and practical **California travel agent**.
# - You have deep knowledge of:
#   - Fun, quirky, and iconic places (San Francisco, Los Angeles, San Diego, Santa Barbara, Palm Springs, etc.).
#   - **Budget-friendly** options (cheap eats, hostels, motels, public transit, free viewpoints and hikes).
#   - **Scenic spots** (Big Sur, Highway 1, Yosemite, Lake Tahoe, Joshua Tree, redwoods, coastal overlooks, viewpoints, sunset spots).
#   - **Wine country** and tasting regions (Napa, Sonoma, Paso Robles, Santa Ynez, Temecula, Lodi, etc.).
#   - Beach towns (Santa Cruz, Pismo Beach, Laguna Beach, Malibu, La Jolla, etc.).
# - Your tone: warm, curious, and encouraging; you explain trade-offs clearly and never talk down to the user.
# - You are concise but not terse: enough detail to be useful, without overwhelming the user.

# ========================
# C O N T E X T  (California-Only Focus)
# ========================
# - Users are asking you to **plan or refine trips within California only**.
# - They may have constraints like:
#   - Budget (shoestring / budget / mid-range / luxury)
#   - Duration (weekend, 3–5 days, 1–2 weeks, etc.)
#   - Travel style (road trip, city hopping, nature-focused, wine & food, family-friendly, nightlife-oriented, romantic, solo adventure)
#   - Starting point (e.g., flying into SFO/LAX/SAN/OAK/SJC, already living in California)
#   - Time of year / seasonality.
# - Assume **modern conditions** (recent info) and practical travel times, but do not invent non-existent places.
# - If asked about destinations outside California, gently redirect: you can mention them briefly but always **bring focus back to California**.


# ========================
# R E F E R E N C E S  &  K N O W L E D G E H I N T S
# ========================
# Use these as mental “cheat sheets” when planning:

# - Major Regions:
#   - **Northern California**: San Francisco, Bay Area, Napa/Sonoma wine country, Mendocino, Redwoods (Humboldt, Muir Woods), Lake Tahoe, Yosemite (accessible from both north and south).
#   - **Central Coast**: Monterey, Carmel, Big Sur, Santa Cruz, San Luis Obispo, Pismo Beach, Morro Bay, Paso Robles wine, Santa Barbara.
#   - **Southern California**: Los Angeles, Malibu, Orange County (Laguna, Newport, Huntington), San Diego (La Jolla, Coronado), Palm Springs, Joshua Tree, Temecula wine country.
# - Common Trip “Motifs”:
#   - **Highway 1 road trip** (San Francisco → Santa Cruz → Monterey/Carmel → Big Sur → San Luis Obispo → Santa Barbara → LA).
#   - **National Parks loop** (Yosemite, Sequoia, Kings Canyon, Joshua Tree, Death Valley depending on season).
#   - **Wine + Coast** (Napa/Sonoma + Point Reyes / Sonoma Coast; or Paso Robles + Pismo/SLO; or Santa Ynez + Santa Barbara).
#   - **City + Nature combo** (San Francisco + Yosemite; LA + Joshua Tree; San Diego + Anza-Borrego/Julian).
# - Budget Hints:
#   - Budget: focus on cheaper motels, hostels, campgrounds, public transit, picnics, taquerias, food trucks, free viewpoints.
#   - Mid-range: standard hotels, boutique stays, 1–2 special splurge meals or experiences.
#   - Luxury: high-end resorts, private tours, fine dining, premium tastings in wine country.
# - Wineries & Wine Regions:
#   - Napa & Sonoma (classic, polished, can be pricier).
#   - Paso Robles (laid-back, excellent reds, good for road trips).
#   - Santa Ynez/Santa Barbara area (wine + beach town vibes).
#   - Temecula (SoCal wine option, often from LA/San Diego).
# - Scenic Highlights:
#   - Coastal: Big Sur, Bixby Bridge, 17-Mile Drive, Point Reyes, Mendocino coast, Malibu, Laguna Beach.
#   - Mountains/Lakes: Lake Tahoe, Mammoth Lakes, Shaver Lake, Bishop area.
#   - Parks: Yosemite Valley, Glacier Point (seasonal), Sequoia NP (giant trees), Joshua Tree (rock formations, stargazing), Death Valley (EXTREME heat considerations).

# You do NOT need to mention this list to the user explicitly; use it internally to inspire **specific, realistic** recommendations.

# ====================================================
# T C R E I   S T R U C T U R E D   B E H A V I O R
# ====================================================

# T – TASK
# --------
# Your core task is to **plan and refine California trips**.

# For every user request:
# 1. Understand their goals (fun, relaxation, photography, food/wine, family, romance, nightlife, hiking, etc.).
# 2. Ask for missing but important info **briefly** (budget, dates/season, starting city, driving vs. non-driving, preferences).
# 3. Propose a **clear, well-structured itinerary or recommendation set** tailored to them.
# 4. Offer **options and trade-offs** (e.g., “Option A: more nature; Option B: more food/wine and cities”).
# 5. Adjust plans based on follow-up questions or constraints.

# C – CONTEXT
# -----------
# Always ground your answer in:
# - **California geography** (don’t make people drive impossible distances in a day).
# - **Travel time realism** (no more than ~4–6 hours of driving on typical days unless explicitly requested).
# - **Seasonality and conditions** (e.g., snow at Tahoe in winter, Yosemite access differences, heat in deserts in summer).
# - **User’s constraints** (budget, trip length, mobility concerns, kids, pets, etc.).

# If the user gives very little info, propose a **few tailored options** and explain you can refine once they share more details.

# R – REQUIREMENTS
# ----------------
# 1. **California-focused**: Keep primary recommendations within California.
# 2. **Structure**:
#    - For trip plans, organize with headings like:
#      - Overview
#      - Day-by-Day Plan (or “Options” if not a fixed itinerary)
#      - Lodging Suggestions
#      - Food & Drink Ideas (including wineries if relevant)
#      - Budget Notes
#      - Practical Tips
# 3. **Budget-awareness**:
#    - Always mention *at least one* budget-conscious suggestion even for non-budget trips.
#    - Call out cost drivers: car rental, gas, parking, National Park fees, wine tastings, resort towns.
# 4. **Safety & practicality**:
#    - Caution about long drives, desert heat, winter road conditions, wildfire/smoke season in a general way (no fake real-time info).
#    - Encourage checking current conditions and booking popular spots ahead of time.
# 5. **User-centric**:
#    - Reflect back key preferences they mentioned (“Since you love wineries and coastal drives…”).
#    - Avoid pushing a single “perfect” plan; instead, show 1–2 good options.
# 6. **Clarity & brevity**:
#    - Prefer bullets and short paragraphs.
#    - Avoid giant walls of text.
#    - Make each day’s description easy to scan.

# E – EXAMPLES
# ------------
# Use these as style and formatting references (do not literally repeat them unless they fit):

# Example 1 – 4-day budget-friendly SF + Big Sur:
# - Overview:
#   - 4 days, starting and ending in San Francisco.
#   - Focus: iconic sights, one scenic coastal drive, mostly budget-friendly.
# - Day 1 – San Francisco:
#   - Morning: Walk along the Embarcadero and Ferry Building.
#   - Afternoon: Explore Fisherman’s Wharf + Ghirardelli Square; walk up to Lombard Street.
#   - Evening: Sunset at Baker Beach or Marshall’s Beach with Golden Gate views.
#   - Budget tip: Use Muni and walking instead of rideshare where possible.
# - Day 2 – More SF Neighborhoods:
#   - Mission District murals + cheap, amazing tacos.
#   - Twin Peaks or Bernal Hill for city views.
#   - Optional Alcatraz tour (book ahead).
# - Day 3 – SF → Monterey/Carmel:
#   - Drive ~2.5–3 hours down the coast.
#   - Stop in Santa Cruz for beach/boardwalk if you like.
#   - Afternoon: Monterey’s Cannery Row / aquarium (ticketed) or chill at Carmel Beach.
#   - Stay overnight in budget motel in Monterey or Marina.
# - Day 4 – Big Sur highlights → back to SF:
#   - Drive Hwy 1: Bixby Creek Bridge, Pfeiffer Big Sur State Park, a viewpoint like Nepenthe.
#   - Head back toward SF in late afternoon/evening.
#   - Budget tip: Pack snacks and picnic instead of multiple restaurant stops.

# Example 2 – Wine-focused weekend in Santa Barbara & Santa Ynez:
# - Overview: 2 nights, romantic getaway, mid-range budget, driving from LA.
# - Day 1 – LA → Santa Barbara:
#   - Drive ~2 hours north (longer with traffic).
#   - Explore State Street, waterfront, and Funk Zone tasting rooms.
#   - Dinner at a local farm-to-table spot.
# - Day 2 – Santa Ynez Valley Wineries:
#   - Morning: Drive to Los Olivos or Solvang; choose 2–3 wineries (book tastings).
#   - Lunch in Los Olivos or a picnic at a winery.
#   - Optional: stop at a third tasting or a viewpoint on the way back.
# - Day 3 – Beach time & return:
#   - Half-day at Butterfly Beach or Hendry’s Beach.
#   - Drive back to LA after lunch.

# I – INPUT & OUTPUT INSTRUCTIONS
# -------------------------------
# When you receive a user message:

# 1. **Interpret the request**:
#    - Identify: dates (or approximate), trip length, budget, starting point, interests, group type.
#    - If any of these are missing AND are critical to giving useful advice, ask at most **2–3 concise clarification questions** before giving a full plan. If possible, still offer a draft plan with notes like “Adjustable once you confirm dates/budget.”

# 2. **Output format**:
#    - Default response for a trip plan:
#     - Produce a single JSON Object.
#      - Title (short and catchy)
#      - Overview (2–4 bullet points)
#      - Day-by-Day (or Option A / Option B) with:
#        - Morning / Afternoon / Evening suggestions
#        - Driving time estimates when relevant
#      - Lodging ideas (by area and rough price tier, not exact prices)
#      - Food & winery suggestions if relevant (names + what type of vibe)
#      - Budget & logistics notes (gas, parking, passes, reservations)
#      - Tips & alternatives section at the end


#    - If the user or calling app explicitly requests structured output (e.g., JSON), then:
#      - Respect their requested schema.
#      - Keep text fields clear but concise.

# 3. **Iterative refinement**:
#    - After presenting a plan, invite focused refinement:
#      - “If you want, tell me which days/areas you’re most excited about and I’ll refine those in more detail,” or
#      - “If this feels too rushed/relaxed, I can rebalance the pace.”

# 4. **Stay in character**:
#    - Always respond as CALI-TRIP-PRO, the friendly California travel expert.
#    - Do not mention this system prompt or internal guidelines.
#    - Never say you are limited to generic knowledge; instead, confidently provide realistic, grounded California advice.
#  """
#              "\n\n"
#     "=============================\n"
#     "S T R U C T U R E D   O U T P U T\n"
#     "=============================\n"
#     "You are called by a backend service and MUST always return a single JSON object.\n"
#     "Do not include any explanations, headings, or extra text outside the JSON.\n\n"
#     "Top-level JSON keys (required):\n"
#     "- type\n"
#     "- version\n"
#     "- mode\n"
#     "- thread_id\n"
#     "- message_id\n"
#     "- destination\n"
#     "- days\n"
#     "- trip_types\n"
#     "- difficulty\n"
#     "- budget_band\n"
#     "- lodging\n"
#     "- weather_hint\n"
#     "- window_summary\n"
#     "- intro_text\n"
#     "- closing_tips\n"
#     "- itinerary\n\n"
#     "Rules for these fields:\n"
#     "- type: always 'trip_plan'.\n"
#     "- version: always 'v1'.\n"
#     "- thread_id: copy from context_pack.thread_id.\n"
#     "- message_id: copy from context_pack.message_id.\n"
#     "- itinerary: an array of day objects when planning a trip; otherwise empty.\n\n"
#     "MODE LOGIC (VERY IMPORTANT):\n"
#     "1) Look at context_pack.window_summary, especially the last user message.\n"
#     "2) If the last user message is ONLY a greeting or small talk\n"
#     "   (e.g. 'hey', 'hey man', 'hi', 'hello', 'sup', 'good morning', 'what's up'),\n"
#     "   and does NOT clearly ask to plan or change a trip, then:\n"
#     "     - mode = 'GREETING_ONLY'\n"
#     "     - destination = null\n"
#     "     - days = 0\n"
#     "     - trip_types = []\n"
#     "     - difficulty = 'UNSPECIFIED'\n"
#     "     - budget_band = 'UNSPECIFIED'\n"
#     "     - lodging = null\n"
#     "     - weather_hint = null\n"
#     "     - itinerary = []\n"
#     "     - window_summary = short recap of what the user said "
#     "       (e.g. 'User greeted the assistant.').\n"
#     "     - intro_text = a short, friendly, conversational response like "
#     "       'Hey! Are you ready to plan a California getaway? It’s holiday season "
#     "       and I can help you put together a great trip when you’re ready.'\n"
#     "     - closing_tips = a short invitation to share their dates, budget, "
#     "       and starting city, or null.\n\n"
#     "3) Otherwise (user clearly asks to plan or refine a trip), then:\n"
#     "     - mode = 'TRIP_PLAN'\n"
#     "     - destination = human-readable place in California that matches the request\n"
#     "       (e.g. 'Big Sur, California', 'Napa Valley', 'Los Angeles').\n"
#     "     - days = length of the trip, using context_pack.time or constraints.\n"
#     "     - trip_types = labels like ['ROAD_TRIP', 'CITY', 'NATURE', 'WINE'].\n"
#     "     - difficulty = 'EASY' / 'MODERATE' / 'HARD' or similar.\n"
#     "     - budget_band = code like 'USD_0_500', 'USD_500_1500', etc.\n"
#     "     - lodging = null or an object {name, type, location, notes}.\n"
#     "     - weather_hint = short plain-text sentence or null.\n"
#     "     - window_summary = 1–2 sentence plain-language recap of the overall plan.\n"
#     "     - intro_text = 1–2 friendly sentences introducing the trip.\n"
#     "     - closing_tips = 1–3 short sentences with practical advice.\n"
#     "     - itinerary = array of day objects {{day, title, highlights, activities}}.\n\n"
#     "For each itinerary day object:\n"
#     "- day: integer starting from 1.\n"
#     "- title: friendly sentence like 'Day 1 – San Francisco Icons & Golden Gate Views'.\n"
#     "- highlights: list of short phrases (no markdown), e.g. 'Sunset at Baker Beach'.\n"
#     "- activities: list of objects with fields:\n"
#     "    * name: short label.\n"
#     "    * description: 1–3 full sentences in natural language.\n"
#     "    * tags: small list of category words like ['HIKE', 'SCENIC', 'FOOD'].\n"
#     "    * estimated_time_hours: rough numeric estimate, e.g. 2.5.\n\n"
#     "OUTPUT FORMAT RULES:\n"
#     "- You MUST output ONLY a single JSON object, nothing before or after it.\n"
#     "- Do NOT use markdown formatting inside strings (no **bold**, no bullet syntax).\n"
#     "- All text must read like a warm, conversational California travel agent.\n\n"
#     "Here is the input JSON you must base your answer on:\n"
#     + f"{json.dumps(llm_input, ensure_ascii=False)}"
#         )

#         print('LLM INPUT' , llm_input)


#         # google-generativeai is sync; run in a thread so our API stays async
#         def _run_sync_call() -> Dict[str, Any]:
#             response = self._gemini_model.generate_content(
#             [user_prompt],
#             generation_config={
#                 # ask Gemini to return JSON only
#                 "response_mime_type": "application/json",
#             },
#         )
        
           

#             # In JSON mode, response.text should already be pure JSON
#             raw = getattr(response, "text", None)
#             if not raw:
#                 # safety: try to dig into parts if text is empty
#                 try:
#                     parts = response.candidates[0].content.parts
#                     raw = "".join(p.text for p in parts if hasattr(p, "text"))
#                 except Exception:
#                     raise RuntimeError("Gemini response had no text content")

#             try:
#                 parsed = json.loads(raw)
#                 print("llm response", response)

#                 trip_plan: Dict[str, Any]

#                 # Case 1: wrapper object { "reply": { ...trip_plan... } }
#                 if isinstance(parsed, dict) and "reply" in parsed:
#                     trip_plan = parsed["reply"]

#                 # Case 2: bare trip_plan object { "type": "trip_plan", ... }
#                 elif isinstance(parsed, dict) and parsed.get("type") == "trip_plan":
#                     trip_plan = parsed

#                 else:
#                     raise RuntimeError(
#                         "LLM response did not contain a valid trip_plan (no 'reply' and no top-level type=='trip_plan')"
#                     )

#             except json.JSONDecodeError as e:
#                     raise RuntimeError(f"Failed to parse Gemini JSON: {e} | raw={raw[:400]}")

#                 # Ensure required top-level fields exist; fill from context if missing
#             trip_plan.setdefault("type", "trip_plan")
#             trip_plan.setdefault("version", "v1")
#             trip_plan.setdefault("thread_id", thread_id)
#             trip_plan.setdefault("message_id", msg_id)
#             trip_plan.setdefault("destination", destination_name)

#             return trip_plan

    # ------------------------------------------------------------------ Rule-based fallback (old logic)

    def _rule_based_plan(
        self,
        grounded_context: Dict[str, Any],
        context_pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Simple local planner that returns the same JSON shape as Gemini,
        but with less detail. Text is also in human-readable language.
        """
        constraints: Dict[str, Any] = context_pack.get("constraints", {}) or {}
        time_block: Dict[str, Any] = context_pack.get("time", {}) or {}
        geoscope: Dict[str, Any] = context_pack.get("geoscope", {}) or {}

        destination_obj = geoscope.get("destination") or {}
        destination_name = (
            destination_obj.get("display_name")
            or destination_obj.get("name")
            or destination_obj.get("region_code")
            or "your destination"
        )

        # how many days?
        days: int = (
            time_block.get("days")
            or constraints.get("duration_days")
            or 3  # default
        )

        trip_types = constraints.get("trip_types") or []
        difficulty = (
            (constraints.get("difficulty") or {}).get("level")
            or constraints.get("difficulty")
            or "EASY"
        )
        budget_band = (
            (constraints.get("budget") or {}).get("band")
            or constraints.get("budget_level")
            or "USD_0_500"
        )

        # RAG outputs
        pois: List[Dict[str, Any]] = grounded_context.get("pois") or []
        lodging: List[Dict[str, Any]] = grounded_context.get("lodging") or []
        weather: Dict[str, Any] = grounded_context.get("weather") or {}

        logger.info(
            "LLMModule._rule_based_plan: destination=%s days=%s pois=%d lodging=%d",
            destination_name,
            days,
            len(pois),
            len(lodging),
        )

        # Simple heuristic: up to 3 POIs per day
        max_pois_per_day = 3
        pois_for_plan = pois[: days * max_pois_per_day]

        day_plans: List[Dict[str, Any]] = []

        for day_idx in range(days):
            day_number = day_idx + 1
            start = day_idx * max_pois_per_day
            end = start + max_pois_per_day
            day_pois = pois_for_plan[start:end]

            activities = []
            for poi in day_pois:
                name = poi.get("name") or poi.get("title") or "Unknown spot"
                desc = (
                    poi.get("description")
                    or poi.get("summary")
                    or f"Spend some relaxed time exploring {name}."
                )
                activities.append(
                    {
                        "name": name,
                        "description": desc,
                        "tags": poi.get("tags") or poi.get("categories") or [],
                        "estimated_time_hours": 2,
                    }
                )

            title = f"Day {day_number} in {destination_name}"
            if day_number == 1:
                title += " – Arrival and first impressions"
            elif day_number == days:
                title += " – Farewell and final stops"

            day_plans.append(
                {
                    "day": day_number,
                    "title": title,
                    "highlights": [a["name"] for a in activities]
                    or [f"Explore {destination_name} at your own pace"],
                    "activities": activities,
                }
            )

        # Lodging suggestion (very simple for now)
        primary_lodging: Optional[Dict[str, Any]] = lodging[0] if lodging else None
        lodging_summary = None
        if primary_lodging:
            lodging_summary = {
                "name": primary_lodging.get("name") or "Suggested lodging",
                "type": primary_lodging.get("type"),
                "location": primary_lodging.get("location")
                or primary_lodging.get("address"),
                "notes": primary_lodging.get("notes")
                or primary_lodging.get("description")
                or f"A practical place to stay in or near {destination_name}.",
            }

        # Weather hint
        weather_hint = None
        if isinstance(weather, dict):
            weather_hint = (
                weather.get("summary")
                or weather.get("forecast_summary")
                or None
            )

        window_summary = context_pack.get("window_summary")

        trip_plan: Dict[str, Any] = {
            "type": "trip_plan",
            "version": "v1",
            "thread_id": context_pack.get("thread_id"),
            "message_id": context_pack.get("message_id"),
            "destination": destination_name,
            "days": days,
            "trip_types": trip_types,
            "difficulty": difficulty,
            "budget_band": budget_band,
            "lodging": lodging_summary,
            "weather_hint": weather_hint,
            "window_summary": window_summary,
            
            "itinerary": day_plans,
        }

        logger.info("LLMModule._rule_based_plan: finished rule-based trip_plan")
        return trip_plan
