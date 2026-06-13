"""Test local image upload with full pipeline - one at a time with logging."""
import asyncio
import httpx
import json
import sys
import time

BASE = "http://localhost:8000"
TIMEOUT = 45  # 45 seconds per image (upload + imgur + serpapi)


async def test_image(filename):
    """Upload a local image and run the full pipeline."""
    filepath = f"testset/{filename}"
    print(f"\n{'=' * 60}")
    print(f"📤 Testing: {filename}")
    print(f"{'=' * 60}")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            with open(filepath, "rb") as f:
                files = {"file": (filename, f, f"image/{filename.split('.')[-1]}")}
                t0 = time.time()
                r = await c.post(
                    f"{BASE}/api/search/image/upload",
                    params={"max_results": 3},
                    files=files,
                )
                elapsed = time.time() - t0

            if r.status_code == 200:
                d = r.json()
                movie = d.get("movie", {})
                print(f"  ✅ Identified!")
                print(f"  🎬 Title:   {movie.get('title', '?')}")
                print(f"  📅 Year:    {movie.get('year', '?')}")
                print(f"  🆔 IMDb:    {movie.get('imdb_id', 'N/A')}")
                print(f"  🏷️  TMDB:   {movie.get('tmdb_id', 'N/A')}")
                print(f"  📊 Results: {d['total_count']} in {elapsed:.1f}s")
                for res in d.get("results", [])[:3]:
                    print(f"     [{res['resource_type']}] {res['title'][:55]}...")
            elif r.status_code == 404:
                print(f"  ⚠️  Not identified: {r.json().get('detail', '')[:100]}")
            else:
                detail = r.json().get("detail", str(r.text[:200]))
                print(f"  ❌ Error {r.status_code}: {detail}")

    except httpx.TimeoutException:
        print(f"  ⏰ Timeout after {TIMEOUT}s")
    except Exception as e:
        print(f"  ❌ Exception: {type(e).__name__}: {str(e)[:150]}")


async def main():
    print("🎬 CineSeeker - Local Image Test")
    print(f"Server: {BASE}")
    print(f"Timeout: {TIMEOUT}s per image")

    await test_image("p2615193241.webp")
    await test_image("p2898894527.webp")

    print(f"\n{'=' * 60}")
    print("✅ Tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
