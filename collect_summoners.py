import requests
import time
import config
from RiotApiCalls import getPuuid

def collect_summoner_names(start_summoner_name, region_start, tagline, output_file, depth=1):
    api_key = config.api_key
    collected_names = set()
    processed_summoners = set()  # Track which summoners we've already processed
    queued_summoners = set()  # Track which summoners are already in queue
    
    # Queue of summoners to process: (name, tag, current_depth)
    queue = [(start_summoner_name, tagline, 0)]
    queued_summoners.add((start_summoner_name, tagline))
    
    while queue:
        current_name, current_tag, current_depth = queue.pop(0)
        
        # Remove from queued set since we're processing now
        queued_summoners.discard((current_name, current_tag))
        
        # Skip if we've already processed this summoner
        if (current_name, current_tag) in processed_summoners:
            continue
        
        processed_summoners.add((current_name, current_tag))
        print(f"\n{'='*60}")
        print(f"Processing: {current_name}#{current_tag} (Depth: {current_depth + 1}/{depth})")
        print(f"Queue size: {len(queue)} | Collected: {len(collected_names)} | Processed: {len(processed_summoners)}")
        print(f"{'='*60}")
        
        try:
            Summoner = getPuuid(region_start, current_name, current_tag)
            puuid = Summoner['puuid']
            collected_names.add((current_name, current_tag))
            
            # Get last 20 match IDs
            match_url = f"https://{region_start}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
            params = {'start': 0, 'count': 20, 'api_key': api_key}
            MatchIDs = requests.get(match_url, params=params).json()
            
            print(f"Found {len(MatchIDs)} matches")
            
            for idx, MatchId in enumerate(MatchIDs, 1):
                match_data_url = f"https://{region_start}.api.riotgames.com/lol/match/v5/matches/{MatchId}"
                print(f"  Match {idx}/{len(MatchIDs)}: {MatchId}")
                
                try:
                    r = requests.get(match_data_url, params={'api_key': api_key})
                    
                    # Retry logic for rate limiting
                    while r.status_code == 429:
                        print("  Rate limited. Sleeping for 10 seconds...")
                        time.sleep(10)
                        r = requests.get(match_data_url, params={'api_key': api_key})
                    
                    if r.status_code != 200:
                        print(f"  Error: Status code {r.status_code}")
                        continue
                    
                    MatchData = r.json()
                    
                    if 'info' not in MatchData or 'participants' not in MatchData['info']:
                        print(f"  Skipping: Missing data")
                        continue
                    
                    # Collect all participants from this match
                    match_summoners = 0
                    new_queued = 0
                    for participant in MatchData['info']['participants']:
                        name = participant.get('riotIdGameName')
                        tag = participant.get('riotIdTagline', '')
                        if name and tag:
                            collected_names.add((name, tag))
                            match_summoners += 1
                            
                            # Only add to queue if:
                            # 1. We haven't reached max depth yet
                            # 2. Not already processed
                            # 3. Not already in queue
                            if (current_depth + 1) < depth:
                                if (name, tag) not in processed_summoners and (name, tag) not in queued_summoners:
                                    queue.append((name, tag, current_depth + 1))
                                    queued_summoners.add((name, tag))
                                    new_queued += 1
                    
                    print(f"    Added {match_summoners} summoners (+{new_queued} to queue) (Total: {len(collected_names)}, Queue: {len(queue)})")
                    
                except Exception as e:
                    print(f"  Error fetching match {MatchId}: {e}")
                
                time.sleep(1.2)  # Rate limit safety
                
        except Exception as e:
            print(f"Error processing {current_name}#{current_tag}: {e}")
            continue
    
    # Write results
    with open(output_file, 'w', encoding='utf-8') as f:
        for name, tag in sorted(collected_names):
            f.write(f"{name}#{tag}\n")
    
    print(f"\n{'='*60}")
    print(f"=== Collection Complete ===")
    print(f"Processed {len(processed_summoners)} summoners")
    print(f"Collected {len(collected_names)} unique summoner names")
    print(f"Saved to {output_file}")
    print(f"{'='*60}")

if __name__ == "__main__":
    start_summoner_name = "Achillex"
    region_start = "europe"
    tagline = "ADC"
    output_file = "summoner_names.txt"
    depth = 2  # Change this to control how many layers deep to go
    
    collect_summoner_names(start_summoner_name, region_start, tagline, output_file, depth)