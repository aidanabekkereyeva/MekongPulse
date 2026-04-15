"""
Seed script: writes 10 Mekong River news articles into data/news_cache.json.

Articles use real, publicly accessible URLs so users can open them directly.
Summaries and metadata are written for the MekongPulse project.

Run from the project root:
    python scripts/seed_news.py
"""

import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "news_cache.json"


def article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def days_ago(n: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=n)
    return dt.isoformat()


# ── Seed articles with real, publicly accessible URLs ──────────────────────
SEED_ARTICLES = [
    {
        "url": "https://www.nationthailand.com/news/general/40052936",
        "title": "Authorities Urged Flood Prep as Mekong River Levels Rise from Tropical Storm Wipha",
        "source_name": "Nation Thailand",
        "source_url": "https://www.nationthailand.com",
        "published_at": days_ago(2),
        "summary": (
            "Thai authorities issued urgent flood preparation warnings as Mekong River water "
            "levels surged following the passage of Tropical Storm Wipha through Laos. "
            "Stations in Nong Khai recorded levels expected to rise 3–4 metres, potentially "
            "overtopping riverbanks by up to 50 cm. Provinces in northeastern Thailand were "
            "placed on high alert, with evacuation routes pre-positioned for low-lying communities."
        ),
        "content_snippet": (
            "Thai authorities issued urgent flood preparation warnings as Mekong River water "
            "levels surged following Tropical Storm Wipha, with northeastern provinces on high alert."
        ),
        "topic": "Mekong River Floods",
        "country_or_region": "Thailand, Laos",
        "is_flood_related": True,
        "relevance_score": 0.97,
        "tags": ["flooding", "tropical storm", "thailand", "mekong", "flood warning"],
        "image_url": "https://media.nationthailand.com/uploads/images/contents/w1024/2025/07/SKZ6iFnwXPNyVhnMFzLT.webp?x-image-process=style/lg-webp",
    },
    {
        "url": "https://www.rfa.org/english/laos/2025/04/08/laos-hydropower-dam-video-mekong-river-thai/",
        "title": "New Mega-Dam Takes Shape on the Mekong River in Laos",
        "source_name": "Radio Free Asia",
        "source_url": "https://www.rfa.org",
        "published_at": days_ago(7),
        "summary": (
            "Construction of the 1,460-megawatt Luang Prabang hydropower dam is advancing "
            "rapidly about 25 kilometres north of the UNESCO World Heritage city, making it "
            "the third dam to block the main artery of the lower Mekong in Laos. "
            "More than 2,130 families across 23 villages are being relocated to make way for "
            "the reservoir. Experts warn the dam will further disrupt fish migrations and "
            "reduce sediment flows vital to downstream agriculture and the Mekong Delta."
        ),
        "content_snippet": (
            "The 1,460 MW Luang Prabang dam is advancing rapidly, displacing over 2,130 "
            "families and raising concerns over fish migration disruption downstream."
        ),
        "topic": "Mekong River",
        "country_or_region": "Laos, Thailand",
        "is_flood_related": False,
        "relevance_score": 0.94,
        "tags": ["hydropower", "dam", "luang prabang", "mekong", "laos"],
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/a/ae/Mekong_river%2C_Thai-Laos_Border.jpg",
    },
    {
        "url": "https://vietnamnews.vn/society/1688907/mekong-delta-faces-increased-saltwater-intrusion-in-2024-25-dry-season.html",
        "title": "Mekong Delta Faces Increased Saltwater Intrusion in 2024-25 Dry Season",
        "source_name": "Viet Nam News",
        "source_url": "https://vietnamnews.vn",
        "published_at": days_ago(14),
        "summary": (
            "Vietnam's Mekong Delta is experiencing worsening saltwater intrusion during the "
            "2024–25 dry season, driven by reduced upstream freshwater flow, sea-level rise, "
            "and intensive groundwater extraction causing land subsidence. Provincial authorities "
            "in Ben Tre and Tien Giang are urging farmers to store freshwater and shift to "
            "salt-tolerant crops. The delta, which produces over half of Vietnam's rice, faces "
            "growing risks to food security as saline water reaches deeper inland each year."
        ),
        "content_snippet": (
            "Vietnam's Mekong Delta faces worsening saltwater intrusion in the 2024-25 dry "
            "season, threatening rice production and the livelihoods of nearly 20 million people."
        ),
        "topic": "Mekong River",
        "country_or_region": "Vietnam",
        "is_flood_related": False,
        "relevance_score": 0.92,
        "tags": ["mekong delta", "salinity", "vietnam", "drought", "food security"],
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/3/36/Mekong_Delta_ESA510396.jpg",
    },
    {
        "url": "https://english.news.cn/20251001/88494cae054d43f3b3048ba448ebc4eb/c.html",
        "title": "Laos Hit by Widespread Flooding After Days of Heavy Rain",
        "source_name": "Xinhua",
        "source_url": "https://english.news.cn",
        "published_at": days_ago(4),
        "summary": (
            "Widespread flooding struck multiple provinces in Laos after several days of intense "
            "monsoon rainfall, with the Mekong and its tributaries overflowing into agricultural "
            "land and villages. In Savannakhet alone, 18 villages and over 3,000 hectares of "
            "rice fields were inundated, displacing more than 2,600 families. Roads, schools, "
            "and irrigation facilities sustained significant damage as authorities mobilised "
            "relief supplies by boat."
        ),
        "content_snippet": (
            "Widespread flooding struck Laos after heavy monsoon rain, with 18 villages and "
            "3,165 hectares of rice fields flooded in Savannakhet, displacing 2,608 families."
        ),
        "topic": "Mekong River Floods",
        "country_or_region": "Laos",
        "is_flood_related": True,
        "relevance_score": 0.96,
        "tags": ["flooding", "laos", "mekong", "monsoon", "displacement"],
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/9/9a/Flooded_building_and_tree_trunk_in_the_muddy_water_of_the_Mekong_in_Si_Phan_Don%2C_Laos%2C_September_2019.jpg",
    },
    {
        "url": "https://asianews.network/mekong-overflows-in-laos-luang-prabang-further-flooding-expected/",
        "title": "Mekong Overflows in Laos' Luang Prabang, Further Flooding Expected",
        "source_name": "Asia News Network",
        "source_url": "https://asianews.network",
        "published_at": days_ago(3),
        "summary": (
            "The Mekong River overflowed its banks at Luang Prabang in northern Laos, submerging "
            "riverside areas and prompting evacuation warnings for communities downstream. "
            "Meteorologists forecast continued heavy rainfall over the upper basin, raising the "
            "risk of further inundation along the river's path through Thailand and Cambodia. "
            "Local authorities are coordinating with the Mekong River Commission to issue "
            "real-time water level updates to at-risk communities."
        ),
        "content_snippet": (
            "The Mekong overflowed at Luang Prabang in northern Laos, with further flooding "
            "forecast downstream as heavy rains continue over the upper basin."
        ),
        "topic": "Mekong River Floods",
        "country_or_region": "Laos, Thailand, Cambodia",
        "is_flood_related": True,
        "relevance_score": 0.97,
        "tags": ["flooding", "luang prabang", "mekong", "laos", "flood warning"],
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/1/12/Flooded_banks_in_the_muddy_water_of_the_Mekong_with_a_boy%2C_rowing_in_a_repurposed_refrigerator_raft%2C_in_Don_Khon%2C_Laos.jpg",
    },
    {
        "url": "https://www.worldbank.org/en/news/feature/2025/08/12/new-infrastructure-protects-viet-nam-s-mekong-delta-city-from-chronic-floods",
        "title": "New Infrastructure Protects Vietnam's Mekong Delta City from Chronic Floods",
        "source_name": "World Bank",
        "source_url": "https://www.worldbank.org",
        "published_at": days_ago(10),
        "summary": (
            "A World Bank-funded resilience project in Can Tho, Vietnam's largest Mekong Delta "
            "city, has successfully protected 420,000 residents across 2,500 hectares through "
            "new drainage networks and tidal sluice gates. The infrastructure passed its first "
            "major test during the 2023 high-water season, holding back floodwaters that would "
            "previously have inundated central neighbourhoods. The project is part of a broader "
            "strategy to help Mekong Delta cities adapt to rising sea levels and intensifying "
            "floods driven by climate change."
        ),
        "content_snippet": (
            "A World Bank-funded project in Can Tho has protected 420,000 residents from "
            "chronic Mekong Delta flooding through new tidal sluice gates and drainage systems."
        ),
        "topic": "Mekong River Floods",
        "country_or_region": "Vietnam",
        "is_flood_related": True,
        "relevance_score": 0.89,
        "tags": ["flood resilience", "mekong delta", "vietnam", "infrastructure", "climate adaptation"],
        "image_url": "https://worldbank.scene7.com/is/image/worldbankprod/Can-Tho-Urban-Development-and-Resilience-Project-Pham-Thi-Thuy-Yen?wid=780&hei=439&qlt=85,0&resMode=sharp",
    },
    {
        "url": "https://www.circleofblue.org/2025/water-climate/mekong-rivers-condition-is-study-of-competing-trends-decline-and-resilience/",
        "title": "Can the Mekong, the World's Most Productive River, Endure Relentless Strain?",
        "source_name": "Circle of Blue",
        "source_url": "https://www.circleofblue.org",
        "published_at": days_ago(18),
        "summary": (
            "A detailed assessment of the Mekong River finds a system under compounding stress "
            "from upstream dams, climate-driven hydrological shifts, and declining biodiversity, "
            "yet showing pockets of resilience where communities and governments are adapting. "
            "The report documents how the cascade of Chinese dams on the upper Mekong has "
            "fundamentally altered the river's natural flood pulse, with far-reaching "
            "consequences for the 60 million people who depend on its fisheries and floodplains. "
            "Conservationists note rare positive signs, including the return of Mekong giant "
            "catfish to some northern stretches."
        ),
        "content_snippet": (
            "A new assessment finds the Mekong under severe stress from dams and climate change, "
            "yet showing resilience in communities adapting to the river's transformation."
        ),
        "topic": "Mekong River",
        "country_or_region": "China, Laos, Thailand, Cambodia, Vietnam",
        "is_flood_related": False,
        "relevance_score": 0.93,
        "tags": ["mekong", "biodiversity", "hydropower", "climate change", "resilience"],
        "image_url": "https://i0.wp.com/www.circleofblue.org/wp-content/uploads/2025/09/2016-02-Vietnam-Mekong-Can-Tho-JGanter2016-02-23-Vietnam-Mekong-Can-Tho-JCGanter_MG_6341.jpg?fit=2000%2C1334&ssl=1",
    },
    {
        "url": "https://dialogue.earth/en/energy/what-are-the-impacts-of-dams-on-the-mekong-river/",
        "title": "What Are the Impacts of Dams on the Mekong River?",
        "source_name": "Dialogue Earth",
        "source_url": "https://dialogue.earth",
        "published_at": days_ago(21),
        "summary": (
            "A comprehensive analysis of hydropower dam impacts on the Mekong River finds that "
            "if all planned projects are completed, sediment reaching the delta could fall by "
            "up to 97 percent compared to natural levels. The loss of sediment is already "
            "accelerating coastal erosion and reducing the fertility of floodplain farmland. "
            "Fish biomass in the lower Mekong is projected to fall 40–80 percent by 2040, "
            "threatening the primary protein source for tens of millions of people across "
            "Cambodia, Laos, Thailand, and Vietnam."
        ),
        "content_snippet": (
            "Planned dams could reduce Mekong sediment by 97% and cut fish biomass by up to "
            "80% by 2040, threatening food security for tens of millions of people."
        ),
        "topic": "Mekong River",
        "country_or_region": "China, Laos, Cambodia, Thailand, Vietnam",
        "is_flood_related": False,
        "relevance_score": 0.91,
        "tags": ["dam", "sediment", "fisheries", "mekong", "environment"],
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/1/12/Floating_village_in_the_Mekong_river.jpg",
    },
    {
        "url": "https://eastasiaforum.org/2025/11/22/salinity-intrusion-threatens-vietnams-rice-bowl/",
        "title": "Salinity Intrusion Threatens Vietnam's Rice Bowl",
        "source_name": "East Asia Forum",
        "source_url": "https://eastasiaforum.org",
        "published_at": days_ago(5),
        "summary": (
            "Salinity intrusion — once a rare shock — has become an annual hazard in Vietnam's "
            "Mekong Delta, threatening the livelihoods of nearly 20 million people and "
            "undermining one of the world's most important rice-producing regions. Saltwater "
            "is now advancing further inland each dry season, driven by reduced upstream "
            "freshwater flow from Chinese dams, sea-level rise, and accelerating land subsidence. "
            "Policy experts are calling for an integrated Mekong water management framework "
            "that gives downstream countries a formal voice in upstream dam operations."
        ),
        "content_snippet": (
            "Salinity intrusion has become an annual hazard in Vietnam's Mekong Delta, "
            "threatening 20 million livelihoods and calling for cross-border water governance."
        ),
        "topic": "Mekong River",
        "country_or_region": "Vietnam, China",
        "is_flood_related": False,
        "relevance_score": 0.90,
        "tags": ["salinity", "mekong delta", "vietnam", "water governance", "rice"],
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/0/03/Mekong_delta.jpg",
    },
    {
        "url": "https://www.crisisgroup.org/asia/south-east-asia/cambodia-thailand-china/343-dammed-mekong-averting-environmental-catastrophe",
        "title": "Dammed in the Mekong: Averting an Environmental Catastrophe",
        "source_name": "International Crisis Group",
        "source_url": "https://www.crisisgroup.org",
        "published_at": days_ago(30),
        "summary": (
            "The International Crisis Group warns that unchecked hydropower development on the "
            "Mekong risks an environmental catastrophe that will destabilise food and water "
            "security across Southeast Asia. The report estimates that fisheries and sediment "
            "losses caused by lower Mekong mainstream dams total more than $17 billion "
            "cumulatively — far exceeding power revenues. It calls for a mandatory environmental "
            "and social impact review mechanism binding on all six riparian nations, and "
            "immediate suspension of new mainstream dam approvals pending regional consultation."
        ),
        "content_snippet": (
            "The International Crisis Group warns that Mekong dam projects risk environmental "
            "catastrophe, with fisheries losses exceeding $17 billion and threatening regional stability."
        ),
        "topic": "Mekong River",
        "country_or_region": "Cambodia, Thailand, China, Laos, Vietnam",
        "is_flood_related": False,
        "relevance_score": 0.92,
        "tags": ["mekong", "dam", "policy", "environment", "food security"],
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/a/ae/Mekong_river%2C_Thai-Laos_Border.jpg",
    },
]


def build_article(a: dict, now: str) -> dict:
    url = a["url"]
    slug = re.sub(r"[^a-z0-9]+", "-", a["title"].lower())[:80].strip("-")
    return {
        "id": article_id(url),
        "title": a["title"],
        "slug": slug,
        "source_name": a["source_name"],
        "source_url": a["source_url"],
        "article_url": url,
        "canonical_url": url,
        "image_url": a.get("image_url", ""),
        "published_at": a["published_at"],
        "summary": a["summary"],
        "content_snippet": a["content_snippet"],
        "topic": a["topic"],
        "country_or_region": a["country_or_region"],
        "is_flood_related": a["is_flood_related"],
        "relevance_score": a["relevance_score"],
        "tags": a["tags"],
        "raw_payload": {"seeded": True},
        "created_at": now,
        "updated_at": now,
    }


def _parse_dt(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def main() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing = {"articles": [], "last_sync": None, "sync_count": 0}
    if CACHE_PATH.exists():
        try:
            existing = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()
    existing_ids = {a["id"] for a in existing.get("articles", [])}
    seed_built = [build_article(a, now) for a in SEED_ARTICLES]
    new_seeds = [a for a in seed_built if a["id"] not in existing_ids]

    merged = existing.get("articles", []) + new_seeds
    merged.sort(key=lambda x: _parse_dt(x["published_at"]), reverse=True)
    merged = merged[:50]

    result = {
        "articles": merged,
        "last_sync": existing.get("last_sync") or now,
        "sync_count": existing.get("sync_count", 0),
    }

    CACHE_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[seed_news] Added {len(new_seeds)} new seed articles. Total in cache: {len(merged)}")


if __name__ == "__main__":
    main()
