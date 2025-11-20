from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search
import asyncio
import re
import json
import os


# --- Top-level helpers for parsing and inference (moved out of run_limerick_agent for testability)

def try_parse_json_from_texts(texts):
    """Attempt to parse JSON from a list of text fragments. Returns a parsed object or None."""
    if not texts:
        return None
    for t in texts:
        if not isinstance(t, str):
            continue
        s = t.strip()
        # direct parse
        try:
            return json.loads(s)
        except Exception:
            pass
        # try extract smallest balanced json object
        start = s.find('{')
        end = s.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = s[start:end+1]
            try:
                return json.loads(candidate)
            except Exception:
                try:
                    return json.loads(candidate.replace("'", '"'))
                except Exception:
                    pass
    # try combined
    combined = "\n\n".join([t for t in texts if isinstance(t, str)])
    try:
        return json.loads(combined)
    except Exception:
        start = combined.find('{')
        end = combined.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = combined[start:end+1]
            try:
                return json.loads(candidate)
            except Exception:
                try:
                    return json.loads(candidate.replace("'", '"'))
                except Exception:
                    return None
    return None


def infer_years_from_text(text_parts_list):
    """Look through textual outputs and infer (year, share_price, pe_ratio, dividends, market_cap) tuples.
    Returns a list sorted most-recent-first.
    """
    combined = "\n\n".join([t for t in text_parts_list if isinstance(t, str)])
    years_found = []
    for m in re.finditer(r"\b(19|20)\d{2}\b", combined):
        years_found.append((int(m.group(0)), m.start()))
    seen = set()
    years_ordered = []
    for y, pos in sorted(years_found, key=lambda x: (-x[0], x[1])):
        if y not in seen:
            seen.add(y)
            years_ordered.append((y, pos))

    inferred = []
    for y, pos in years_ordered[:5]:
        start = max(0, pos - 250)
        end = min(len(combined), pos + 250)
        snippet = combined[start:end]
        sp_m = re.search(r"([£$€]\s?[\d,]+(?:\.\d+)?)", snippet)
        sp = sp_m.group(1) if sp_m else None
        pe_m = re.search(r"P/?E(?: ratio)?[:\s]*([\d.]+)", snippet, re.IGNORECASE)
        if not pe_m:
            pe_m = re.search(r"\b([\d]{1,3}(?:\.\d+)?)\s*[xX]\b", snippet)
        pe = pe_m.group(1) if pe_m else None
        dv_m = re.search(r"dividends?[:\s]*([\d.]+%?|[\d.]+)", snippet, re.IGNORECASE)
        dv = dv_m.group(1) if dv_m else None
        mc_m = re.search(r"market cap[:\s]*([£$€]?\s?[\d,.]+\s*(?:B|M|bn|m|b)?)", snippet, re.IGNORECASE)
        mc = mc_m.group(1) if mc_m else None
        inferred.append({'year': y, 'share_price': sp, 'pe_ratio': pe, 'dividends': dv, 'market_cap': mc})
    return inferred


def normalize_research_dict(research_obj, text_parts):
    """Normalize a parsed research object into a list of up to 3 year entries (most-recent first).
    Each entry is a dict: {year, share_price, pe_ratio, dividends, market_cap}
    """
    normalized_years = []
    if not research_obj:
        research_obj = {}

    # Case A: explicit 'years' array
    if isinstance(research_obj.get('years'), list):
        for entry in research_obj['years']:
            if isinstance(entry, dict):
                normalized_years.append({
                    'year': entry.get('year'),
                    'share_price': entry.get('share_price') or entry.get('share price') or entry.get('price'),
                    'pe_ratio': entry.get('pe_ratio') or entry.get('pe ratio'),
                    'dividends': entry.get('dividends'),
                    'market_cap': entry.get('market_cap') or entry.get('market cap')
                })

    # Case B: year keys at top level ("2024": {...})
    if not normalized_years and isinstance(research_obj, dict):
        year_keys = [k for k in research_obj.keys() if isinstance(k, str) and k.isdigit() and len(k) == 4]
        for y in sorted(year_keys, reverse=True):
            entry = research_obj.get(y) or {}
            if isinstance(entry, dict):
                normalized_years.append({
                    'year': int(y),
                    'share_price': entry.get('share_price') or entry.get('share price') or entry.get('price'),
                    'pe_ratio': entry.get('pe_ratio') or entry.get('pe ratio'),
                    'dividends': entry.get('dividends'),
                    'market_cap': entry.get('market_cap') or entry.get('market cap')
                })

    # Case C: metric maps (e.g., 'share_price': {'2024': '£x', ...})
    if not normalized_years and isinstance(research_obj, dict):
        metric_keys = ['share_price', 'share price', 'pe_ratio', 'pe ratio', 'dividends', 'market_cap', 'market cap']
        metrics_present = {mk: research_obj.get(mk) for mk in metric_keys if mk in research_obj and isinstance(research_obj.get(mk), dict)}
        if metrics_present:
            years_set = set()
            for mk, md in metrics_present.items():
                years_set.update([y for y in md.keys() if isinstance(y, str) and y.isdigit()])
            for y in sorted(years_set, reverse=True):
                normalized_years.append({
                    'year': int(y),
                    'share_price': (research_obj.get('share_price') or research_obj.get('share price') or {}).get(y),
                    'pe_ratio': (research_obj.get('pe_ratio') or research_obj.get('pe ratio') or {}).get(y),
                    'dividends': (research_obj.get('dividends') or {}).get(y),
                    'market_cap': (research_obj.get('market_cap') or research_obj.get('market cap') or {}).get(y)
                })

    # Case D: flattened single-year
    if not normalized_years:
        if isinstance(research_obj, dict) and (research_obj.get('year') or research_obj.get('share_price') or research_obj.get('share price')):
            latest = {
                'year': research_obj.get('year'),
                'share_price': research_obj.get('share_price') or research_obj.get('share price') or research_obj.get('price'),
                'pe_ratio': research_obj.get('pe_ratio') or research_obj.get('pe ratio'),
                'dividends': research_obj.get('dividends'),
                'market_cap': research_obj.get('market_cap') or research_obj.get('market cap')
            }
            normalized_years.append(latest)

    # Trim to 3 entries if necessary
    if normalized_years:
        normalized_years = normalized_years[:3]

    # If less than 3, try infer from text
    if len(normalized_years) < 3:
        inferred = infer_years_from_text(text_parts)
        existing_years = {e.get('year') for e in normalized_years if e.get('year')}
        for inf in inferred:
            if len(normalized_years) >= 3:
                break
            if inf.get('year') and inf.get('year') not in existing_years:
                normalized_years.append(inf)

    # pad with empty entries to reach 3
    while len(normalized_years) < 3:
        normalized_years.append({'year': None, 'share_price': None, 'pe_ratio': None, 'dividends': None, 'market_cap': None})

    return normalized_years


# --- Agent creation (unchanged)

def create_agents():

    research_agent = Agent(
        model="gemini-2.5-flash",
        name="research_agent",
        description="Researches the performance of a given company",
        instruction="""You are a specialised company research agent.

        Given the name of a publicly traded company, research its performance over the last
        three years and return a machine-readable JSON summary. The JSON MUST contain a
        "years" array with exactly three entries (one per year, most-recent first). Each entry
        must be an object with the keys: 'year' (integer), 'share_price', 'pe_ratio', 'dividends', and 'market_cap'.

        Example output (exact JSON only, no surrounding commentary):
        {
          "years": [
            {"year": 2024, "share_price": "£12.34", "pe_ratio": 15.2, "dividends": "0.45", "market_cap": "£1.2B"},
            {"year": 2023, "share_price": "£10.20", "pe_ratio": 18.1, "dividends": "0.40", "market_cap": "£1.1B"},
            {"year": 2022, "share_price": "£9.50", "pe_ratio": 20.3, "dividends": "0.38", "market_cap": "£1.0B"}
          ]
        }

        IMPORTANT: return ONLY the JSON object (no extra text). If you must include notes, put them in a separate key named 'notes'.
        """,
        tools=[google_search],
        output_key = "research_summary"
    )

    limerick_agent = Agent(
        model="gemini-2.5-flash",
        name="limerick_agent",
        description="Writes a limerick about a given topic",
        instruction="""You are a creative limerick writing agent.
        Given the company research summary (JSON), write a limerick that captures the key points in a humorous way.
        The limerick should follow the traditional AABBA rhyme scheme and be light-hearted and fun.
        Return ONLY the limerick text (no JSON wrapper).
        """,
        output_key = "limerick"
    )

    out_dict = {
        "research_agent": research_agent,
        "limerick_agent": limerick_agent,
    }
    return out_dict


# --- Main runner

def run_limerick_agent(input_company: str) -> dict:
    """Run the research agent then the limerick agent sequentially and return a dict with 'limerick' and 'research'.

    research will be a dict with key 'years' containing up to 3 year entries (most-recent first).
    """
    agent_dict = create_agents()
    research_agent = agent_dict['research_agent']
    limerick_agent = agent_dict['limerick_agent']

    async def run_agent_and_collect(agent, prompt: str):
        runner = InMemoryRunner(agent=agent, app_name="agents")
        try:
            events = await runner.run_debug(prompt, quiet=True)
            parts = []
            for event in events:
                if getattr(event, "content", None) and getattr(event.content, "parts", None):
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            text = part.text.strip()
                            if text:
                                parts.append(text)
            return parts
        finally:
            await runner.close()

    # Run research agent
    try:
        research_texts = asyncio.run(run_agent_and_collect(research_agent, input_company))
    except Exception as e:
        # If the agent runtime is unavailable, return an empty result with an error in limerick
        return {'limerick': '', 'research': {'years': [{'year': None, 'share_price': None, 'pe_ratio': None, 'dividends': None, 'market_cap': None} for _ in range(3)]}, 'error': str(e)}

    # Debug: print raw research_texts
    if os.getenv('LIMERICK_DEBUG') == '1':
        print('DEBUG: raw research_texts:', research_texts)

    research_obj = try_parse_json_from_texts(research_texts)
    if os.getenv('LIMERICK_DEBUG') == '1':
        print('DEBUG: parsed research_obj:', research_obj)

    normalized_years = normalize_research_dict(research_obj, research_texts)
    if os.getenv('LIMERICK_DEBUG') == '1':
        print('DEBUG: normalized_years:', normalized_years)

    # If parsing did not yield 3 real years, retry the research agent with a stricter instruction (up to 2 retries)
    def count_real_years(years_list):
        return sum(1 for y in years_list if y.get('year'))

    retries = 0
    while count_real_years(normalized_years) < 3 and retries < 2:
        retries += 1
        stricter_prompt = (
            f"(ATTEMPT {retries}) Produce ONLY valid JSON. Given the company name '{input_company}', return a JSON object with a top-level 'years' array of exactly three objects (most-recent first). Each object must have keys: year (integer), share_price (string or number or null), pe_ratio (number or null), dividends (string or null), market_cap (string or null). Return JSON only, no explanation.\n\nExample: {json.dumps({'years': [{'year': 2024, 'share_price': '£12.34', 'pe_ratio': 15.2, 'dividends': '0.45', 'market_cap': '£1.2B'}, {'year': 2023, 'share_price': '£10.20', 'pe_ratio': 18.1, 'dividends': '0.40', 'market_cap': '£1.1B'}, {'year': 2022, 'share_price': '£9.50', 'pe_ratio': 20.3, 'dividends': '0.38', 'market_cap': '£1.0B'}]})}"
        )
        try:
            research_texts = asyncio.run(run_agent_and_collect(research_agent, stricter_prompt))
        except Exception:
            break
        research_obj = try_parse_json_from_texts(research_texts)
        normalized_years = normalize_research_dict(research_obj, research_texts)

    # Prepare prompt for limerick agent, include company name for better relevance
    research_for_prompt = {'company': input_company, 'years': normalized_years}
    limerick_prompt = f"Here is company research JSON for {input_company}. Please write a single limerick (AABBA) based only on these facts. Return only the limerick text.\n\n{json.dumps(research_for_prompt)}"

    try:
        limerick_texts = asyncio.run(run_agent_and_collect(limerick_agent, limerick_prompt))
    except Exception as e:
        # Return research but no limerick
        return {'limerick': '', 'research': {'years': normalized_years}, 'error': str(e)}

    if os.getenv('LIMERICK_DEBUG') == '1':
        print('DEBUG: raw limerick_texts:', limerick_texts)

    # Choose the best limerick text (prefer the last non-empty)
    limerick_text = ''
    if limerick_texts:
        # join and pick the non-empty longest chunk
        candidates = [t.strip() for t in limerick_texts if isinstance(t, str) and t.strip()]
        candidates = sorted(candidates, key=lambda s: len(s), reverse=True)
        if candidates:
            limerick_text = candidates[0]

    # Fallback: if model didn't return a limerick, synthesize a simple one using the facts
    if not limerick_text:
        # use the most recent year with data
        yr = next((y for y in normalized_years if y.get('year')), None)
        if yr:
            company = input_company
            sp = yr.get('share_price') or 'an unknown price'
            pe = yr.get('pe_ratio') or 'a curious P/E'
            dv = yr.get('dividends') or 'no tidy dividend'
            mc = yr.get('market_cap') or 'a market cap unknown'
            limerick_text = (
                f"There once was a firm called {company},\n"
                f"Whose shares were at {sp} recently shown;\n"
                f"With P/E about {pe},\n"
                f"And dividends like {dv},\n"
                f"Its market cap was {mc} — all widely known."
            )
        else:
            limerick_text = f"A company called {input_company} was looked up, but the research turned up little to sup."  # minimal fallback

    return {
        'limerick': limerick_text or '',
        'research': {
            'years': normalized_years
        }
    }


if __name__ == "__main__":
    prompt = "Cadburys"  # initial prompt
    output = run_limerick_agent(prompt)
    print("Limerick:", output.get('limerick'))
    print("Research:", output.get('research'))
