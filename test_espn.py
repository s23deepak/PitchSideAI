import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from data_sources.espn_retriever import ESPNDataRetriever

async def main():
    r = ESPNDataRetriever()
    
    print("Fetching Squad for Manchester United...")
    team_data = await r.get_team_squad("Manchester United")
    print("\nTop 5 Players by Appearances:")
    for p in team_data.get("players", [])[:5]:
        print(f"{p['name']} - Apps: {p.get('stats', {}).get('appearances')}, Goals: {p.get('stats', {}).get('goals')}")

    print("\nFetching Form for Manchester United...")
    form_data = await r.get_recent_form("Manchester United", num_games=5)
    print("Recent Form:", form_data.get("form_string"))
    
    print("\nFetching Squad for Liverpool...")
    team_data = await r.get_team_squad("Liverpool")
    print("\nTop 5 Players by Appearances:")
    for p in team_data.get("players", [])[:5]:
        print(f"{p['name']} - Apps: {p.get('stats', {}).get('appearances')}, Goals: {p.get('stats', {}).get('goals')}")

    print("\nFetching Form for Liverpool...")
    form_data = await r.get_recent_form("Liverpool", num_games=5)
    print("Recent Form:", form_data.get("form_string"))


if __name__ == "__main__":
    asyncio.run(main())
