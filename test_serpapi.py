"""Direct SerpApi test - verify the API key works."""
import asyncio
import httpx
import json

SERPAPI_KEY = "b9687056aeeec9b2bad9c145808896bd9b76a379ce6858618a372057e68c1057"

async def test_serpapi():
    print("=" * 60)
    print("Testing SerpApi Google Lens...")
    print("=" * 60)

    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_lens",
        "url": "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg",
    }

    async with httpx.AsyncClient(timeout=25) as c:
        print(f"Requesting: serpapi.com/search (engine=google_lens)")
        r = await c.get("https://serpapi.com/search", params=params)
        print(f"Status: {r.status_code}")

        if r.status_code != 200:
            print(f"HTTP Error: {r.text[:300]}")
            return

        data = r.json()
        error = data.get("error")
        if error:
            print(f"API Error: {error}")
            return

        print(f"\n=== Knowledge Graph ===")
        kg = data.get("knowledge_graph", {})
        if kg:
            print(f"  Title:       {kg.get('title', 'N/A')}")
            print(f"  Type:        {kg.get('type', 'N/A')}")
            print(f"  Description: {str(kg.get('description', 'N/A'))[:100]}")
        else:
            print(f"  (no knowledge graph)")

        print(f"\n=== Visual Matches ({len(data.get('visual_matches', []))}) ===")
        for i, v in enumerate(data.get("visual_matches", [])[:5]):
            title = v.get("title") or v.get("source") or "?"
            print(f"  {i+1}. {str(title)[:60]}")

        print(f"\n=== Top Results ===")
        for i, res in enumerate(data.get("top_results", [])[:3]):
            print(f"  {i+1}. {res.get('title', '?')}")

        print(f"\n✅ SerpApi test complete!")
        print(f"   Full response keys: {list(data.keys())}")

        # Also test the Yandex free method
        print(f"\n{'=' * 60}")
        print(f"Testing Yandex Image Search (free)...")
        print(f"{'=' * 60}")
        yandex_url = "https://yandex.com/images/search"
        yparams = {
            "rpt": "imageview",
            "url": "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg",
            "format": "json",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }
        try:
            ry = await c.get(yandex_url, params=yparams, headers=headers)
            print(f"Yandex Status: {ry.status_code}")
            if ry.status_code == 200:
                # Check if we got meaningful content
                text_len = len(ry.text)
                print(f"Yandex Response: {text_len} bytes")
                print(f"  First 200 chars: {ry.text[:200]}")
            else:
                print(f"Yandex Error: {ry.status_code}")
        except Exception as e:
            print(f"Yandex Exception: {e}")

asyncio.run(test_serpapi())
