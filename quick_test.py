"""Quick SerpApi image search test."""
import asyncio, httpx, json

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # Test 1: Image search with Inception poster
        print("=" * 50)
        print("TEST 1: Image Search - Inception Poster")
        print("=" * 50)
        url = "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg"
        r = await c.get("http://localhost:8000/api/search/image",
                        params={"image_url": url, "max_results": 3})
        d = r.json()
        if r.status_code == 200:
            m = d.get("movie", {})
            print(f"  Movie: {m.get('title')} ({m.get('year')})")
            print(f"  IMDb: {m.get('imdb_id')}")
            print(f"  TMDB: {m.get('tmdb_id')}")
            print(f"  Poster: {m.get('poster_url', 'N/A')[:60]}")
            print(f"  Results: {d['total_count']} ({d['search_time_ms']}ms)")
            for res in d.get("results", [])[:3]:
                print(f"    [{res['resource_type']}] {res['title'][:55]}...")
        else:
            print(f"  Status {r.status_code}: {d.get('detail', str(d))[:200]}")

        # Test 2: Quick text search
        print()
        print("=" * 50)
        print("TEST 2: Text Search - Inception 2010")
        print("=" * 50)
        r = await c.get("http://localhost:8000/api/search",
                        params={"q": "Inception 2010", "max_results": 3})
        d = r.json()
        if r.status_code == 200:
            print(f"  Results: {d['total_count']} ({d['search_time_ms']}ms)")
            print(f"  Sources: {d['sources_used']}")
            for res in d.get("results", [])[:3]:
                print(f"    [{res['resource_type']}] {res['title'][:55]}...")
                print(f"      URL: {res['url'][:70]}...")
        else:
            print(f"  Status {r.status_code}")

        # Test 3: Sources
        print()
        print("=" * 50)
        print("TEST 3: Available Sources")
        print("=" * 50)
        r = await c.get("http://localhost:8000/api/sources")
        d = r.json()
        for s in d["sources"]:
            icon = "+" if s["enabled"] else "x"
            print(f"  [{icon}] [{s['type']:12}] {s['name']}")

asyncio.run(main())
