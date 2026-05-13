"""Debug image search - test URL vs upload."""
import asyncio
import base64
import httpx
import json

BASE = "http://localhost:8000"
SERPAPI_KEY = "b9687056aeeec9b2bad9c145808896bd9b76a379ce6858618a372057e68c1057"


async def test_url_search():
    """Test with known movie poster URL."""
    print("=" * 60)
    print("TEST 1: URL Image Search (Inception poster)")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30) as c:
        url = "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg"
        r = await c.get(f"{BASE}/api/search/image",
                        params={"image_url": url, "max_results": 3})
        if r.status_code == 200:
            d = r.json()
            m = d.get("movie", {})
            print(f"  OK - Movie: {m.get('title')} ({m.get('year')})")
            print(f"  Results: {d['total_count']}")
        else:
            print(f"  {r.status_code}: {r.json().get('detail', '')[:150]}")


async def test_serpapi_direct():
    """Directly test serpapi with the test image."""
    print("\n" + "=" * 60)
    print("TEST 2: SerpApi direct with local image (via serpapi package)")
    print("=" * 60)

    from serpapi import GoogleSearch

    with open("testset/p2615193241.webp", "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_lens",
        "image_base64": b64,
    }

    def search():
        search = GoogleSearch(params)
        return search.get_dict()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, search)

    error = data.get("error")
    if error:
        print(f"  Error: {error}")
        return

    vms = data.get("visual_matches", [])
    print(f"  Visual matches: {len(vms)}")
    for i, v in enumerate(vms[:5]):
        t = v.get("title") or v.get("source", "?")
        print(f"    {i+1}. {str(t)[:70]}")

    kg = data.get("knowledge_graph", {})
    if kg:
        print(f"  Knowledge Graph: {kg.get('title')}")


async def test_upload():
    """Test upload endpoint with test image."""
    print("\n" + "=" * 60)
    print("TEST 3: Upload endpoint with test image")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30) as c:
        with open("testset/p2615193241.webp", "rb") as f:
            files = {"file": ("test.webp", f, "image/webp")}
            r = await c.post(
                f"{BASE}/api/search/image/upload",
                params={"max_results": 3},
                files=files,
            )
        if r.status_code == 200:
            d = r.json()
            m = d.get("movie", {})
            print(f"  OK - Movie: {m.get('title')} ({m.get('year')})")
            print(f"  Results: {d['total_count']}")
        else:
            print(f"  {r.status_code}: {r.json().get('detail', '')[:150]}")


async def main():
    await test_url_search()
    await test_serpapi_direct()
    await test_upload()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
