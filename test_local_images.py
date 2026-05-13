"""Test CineSeeker image search with local testset images via upload API."""
import asyncio
import httpx
import pathlib

BASE = "http://localhost:8000"
TESTSET = pathlib.Path("testset")


async def upload_and_search(filename: str):
    """Upload an image and run image search."""
    filepath = TESTSET / filename
    if not filepath.exists():
        print(f"  ❌ File not found: {filename}")
        return

    print(f"\n📤 Uploading: {filename} ({filepath.stat().st_size/1024:.0f} KB)")
    print(f"{'─' * 60}")

    async with httpx.AsyncClient(timeout=35) as c:
        with open(filepath, "rb") as f:
            files = {"file": (filename, f, f"image/{filename.split('.')[-1]}")}
            r = await c.post(
                f"{BASE}/api/search/image/upload",
                params={"max_results": 3},
                files=files,
            )

        if r.status_code == 200:
            d = r.json()
            movie = d.get("movie", {})
            print(f"  🎬  Identified: '{movie.get('title')}' ({movie.get('year', '?')})")
            print(f"     IMDb: {movie.get('imdb_id', 'N/A')} | TMDB: {movie.get('tmdb_id', 'N/A')}")
            if movie.get("poster_url"):
                print(f"     Poster: {movie['poster_url'][:80]}")
            if movie.get("overview"):
                overview = movie["overview"][:120]
                print(f"     Overview: {overview}...")

            print(f"     📊 Search: {d['total_count']} results in {d['search_time_ms']}ms")
            print(f"     Sources: {d['sources_used']}")

            for res in d.get("results", [])[:3]:
                print(f"       [{res['resource_type']}] {res['title'][:60]}...")

            if d.get("from_cache"):
                print(f"     💾 Cached: {d['from_cache']}")

        elif r.status_code == 404:
            print(f"  ⚠️  {r.json().get('detail', 'Not identified')}")
        else:
            print(f"  ❌ Error {r.status_code}: {str(r.json())[:200]}")


async def main():
    print("=" * 60)
    print("🎬 CineSeeker - Local Image Test Suite")
    print("=" * 60)

    # Get all images from testset
    if not TESTSET.exists():
        print("❌ testset/ directory not found!")
        return

    images = sorted(TESTSET.glob("*"))
    print(f"\n📁 Found {len(images)} images in testset/")

    # Test each image
    for img in images:
        await upload_and_search(img.name)

    print(f"\n{'=' * 60}")
    print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
