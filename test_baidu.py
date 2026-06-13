"""Test image search with Baidu image URL."""
import asyncio
import httpx
import json

IMG_URL = "https://img1.baidu.com/it/u=4131124688,2250564438&fm=253&app=138&f=JPEG?w=800&h=1200"
BASE = "http://localhost:8000"


async def test():
    print("=" * 60)
    print(f"Testing Baidu Image URL")
    print(f"URL: {IMG_URL[:80]}...")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=35) as c:
        t0 = asyncio.get_event_loop().time()

        r = await c.get(
            f"{BASE}/api/search/image",
            params={"image_url": IMG_URL, "max_results": 5},
        )

        elapsed = asyncio.get_event_loop().time() - t0
        d = r.json()

        if r.status_code == 200:
            movie = d.get("movie", {})
            print(f"\n✅ Identified! ({elapsed:.1f}s)")
            print(f"  Title:   {movie.get('title', '?')}")
            print(f"  Year:    {movie.get('year', '?')}")
            print(f"  IMDb:    {movie.get('imdb_id', 'N/A')}")
            print(f"  Poster:  {str(movie.get('poster_url', 'N/A'))[:60]}")
            print(f"  Results: {d['total_count']} in {d['search_time_ms']}ms")
            print(f"  Sources: {d['sources_used']}")
            for res in d.get("results", [])[:3]:
                print(f"    [{res['resource_type']}] {res['title'][:60]}...")
        else:
            detail = d.get("detail", str(d)[:300])
            print(f"\n❌ Status {r.status_code}: {detail}")


if __name__ == "__main__":
    asyncio.run(test())
