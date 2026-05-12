"""Quick test script for CineSeeker API endpoints."""

import asyncio
import httpx
import json
import pathlib

BASE = "http://localhost:8000"


async def test_health():
    print("\n=== 1. Health Check ===")
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get(f"{BASE}/api/health")
        print(f"  ✅ Status: {r.status_code}, Service: {r.json()['service']}")


async def test_sources():
    print("\n=== 2. Available Sources ===")
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get(f"{BASE}/api/sources")
        data = r.json()
        enabled = [s for s in data['sources'] if s['enabled']]
        for s in enabled:
            print(f"  ✅ [{s['type']}] {s['name']}")
        print(f"  Total enabled: {len(enabled)}/{len(data['sources'])}")


async def test_admin_stats():
    print("\n=== 3. Admin Stats ===")
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get(f"{BASE}/api/admin/stats")
        if r.status_code == 200:
            d = r.json()
            print(f"  ✅ Version: {d['version']}")
            print(f"  ✅ DB configured: {d.get('movies_total', 'check .env')}")
        else:
            print(f"  ⚠️  Stats: {r.status_code}")


async def test_local_images():
    """Show local testset images info."""
    print("\n=== 4. Local Testset Images ===")
    testset_dir = pathlib.Path("testset")
    if testset_dir.exists():
        images = sorted(testset_dir.glob("*"))
        if images:
            for img in images:
                size = img.stat().st_size
                print(f"     📷 {img.name} ({size/1024:.0f} KB)")
        else:
            print(f"  ⚠️  No images in testset/")
    else:
        print(f"  ⚠️  testset/ directory not found")


async def test_text_search():
    """Test text search with short timeout."""
    print("\n=== 5. Text Search: 'Inception 2010' ===")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{BASE}/api/search?q=Inception+2010&max_results=5")
        if r.status_code == 200:
            d = r.json()
            print(f"  ✅ {d['total_count']} results in {d['search_time_ms']}ms")
            print(f"     Sources: {d['sources_used']}")
            if d['results']:
                for res in d['results'][:3]:
                    print(f"     [{res['resource_type']}] {res['title'][:55]}... ★{res.get('quality_score', 0)}")
            else:
                print(f"     (external sites may be unreachable)")
        else:
            print(f"  ⚠️  Status {r.status_code}")


async def test_image_search():
    """Test image search with a known movie poster."""
    print("\n=== 6. Image Search ===")
    poster = "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg"

    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.get(
            f"{BASE}/api/search/image",
            params={"image_url": poster, "max_results": 3}
        )
        if r.status_code == 200:
            d = r.json()
            movie = d.get('movie', {})
            print(f"  ✅ Movie: '{movie.get('title')}' ({movie.get('year')})")
            print(f"     IMDb: {movie.get('imdb_id')}")
            print(f"     Results: {d['total_count']} in {d['search_time_ms']}ms")
            for res in d['results'][:2]:
                print(f"     [{res['resource_type']}] {res['title'][:55]}...")
        elif r.status_code == 404:
            print(f"  ⚠️  {r.json()['detail'][:100]}")
        else:
            d = r.json()
            print(f"  ⚠️  Status {r.status_code}: {d.get('detail', str(d))[:120]}")


async def test_full_health():
    print("\n=== 7. Full Health Check ===")
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get(f"{BASE}/api/admin/health/full")
        if r.status_code == 200:
            d = r.json()
            print(f"  ✅ Status: {d['status']}")
            for k, v in d.get('checks', {}).items():
                icon = "✅" if v == 'ok' else "⚠️"
                print(f"     {icon} {k}: {v}")
        else:
            print(f"  ⚠️  Full health: {r.status_code}")


async def main():
    print("=" * 60)
    print("🎬 CineSeeker API Test Suite")
    print("=" * 60)

    await test_health()
    await test_sources()
    await test_admin_stats()
    await test_local_images()
    await test_full_health()

    print("\n" + "-" * 40)
    print("🌐 External API Tests")
    print("-" * 40)

    await test_text_search()
    await test_image_search()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
