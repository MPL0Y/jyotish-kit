"""
JyotishKit Quickstart Example: Compute a chart and inspect planetary dignities in 5 lines.
"""

from jyotish_kit import Jyotish

# 1. Initialize with birth coordinates and time
chart = Jyotish.create(
    dt_local="2001-10-11T05:57:30",
    lat=29.681312,
    lon=77.010063,
    tz_name="Asia/Kolkata",
    place_name="Karnal, Haryana, India",
    ayanamsa="LAHIRI",
)

# 2. Get high-level planetary states
planets = chart.get_planets()
print("=== PLANETARY STATES ===")
for planet, data in planets.items():
    print(f"{planet:10} -> {data['sign']:12} {data['degree']:>7.2f}° | House: {data['house']} | Dignity: {data['dignity']}")

# 3. Get Ashtakavarga bindus
ashtaka = chart.get_ashtakavarga()
print("\n=== SARVASHTAKAVARGA (SAV) ===")
print("SAV bindus by house:", ashtaka["SAV"])

# 4. Check active Vimshottari dasha
dashas = chart.get_dashas("vimshottari", depth=2)
print("\n=== RUNNING & UPCOMING DASHAS (Sample) ===")
for d in dashas[:5]:
    print(f"[{d['level']}] {' / '.join(d['lords']):<20} {d['start'][:10]} -> {d['end'][:10]}")
