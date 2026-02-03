import mysql.connector
import time
import requests
from datetime import datetime
from collections import deque
from config import RIOT_API_KEY

# --- Configuration ---
REGION = 'euw1'
ROUTING_REGION = 'europe'

db_config = {
    'host': 'localhost',
    'port': 3306,
    'database': 'LeagueStatsInterval',
    'user': 'league_user',
    'password': 'StrongPassword123!',
    'autocommit': False,
    'auth_plugin': 'mysql_native_password'
}

class RiotAPIClient:
    def __init__(self, key):
        self.headers = {'X-Riot-Token': key}
        self.rate_limiter = deque()

    def _wait_for_rate_limit(self):
        now = time.time()
        while self.rate_limiter and self.rate_limiter[0] < now - 1.0:
            self.rate_limiter.popleft()
        if len(self.rate_limiter) >= 15:  # Conservative buffer for 20/sec limit
            time.sleep(1.0)
        self.rate_limiter.append(time.time())

    def req(self, url):
        self._wait_for_rate_limit()
        res = requests.get(url, headers=self.headers)
        
        if res.status_code == 429:
            retry_after = int(res.headers.get("Retry-After", 10))
            print(f"Rate limited! Sleeping for {retry_after} seconds...")
            time.sleep(retry_after)
            return self.req(url) # Retry
            
        if res.status_code == 200:
            return res.json()
        else:
            print(f"Error {res.status_code} for {url}: {res.text[:100]}")
            return None

class DatabaseManager:
    def __init__(self, config):
        self.conn = mysql.connector.connect(**config)
        self.cursor = self.conn.cursor(dictionary=True)

    def insert_intervals(self, match_id, player_map, timeline):
        objs = {
            100: {'tk':0,'dt':0,'df':0,'dw':0,'de':0,'da':0,'dc':0,'dx':0,'b':0,'v':0,'h':0,'t':0,'i':0},
            200: {'tk':0,'dt':0,'df':0,'dw':0,'de':0,'da':0,'dc':0,'dx':0,'b':0,'v':0,'h':0,'t':0,'i':0}
        }
        p_stats = {pid: {'k':0,'d':0,'a':0} for pid in player_map}
        p_inv = {pid: [] for pid in player_map}

        for frame_idx, frame in enumerate(timeline['info']['frames']):
            for event in frame.get('events', []):
                etype = event.get('type')
                pid = event.get('participantId')

                if etype == 'ITEM_PURCHASED' and pid in p_inv:
                    if len(p_inv[pid]) < 7: p_inv[pid].append(event['itemId'])
                elif etype in ('ITEM_SOLD', 'ITEM_DESTROYED') and pid in p_inv:
                    if event['itemId'] in p_inv[pid]: p_inv[pid].remove(event['itemId'])
                elif etype == 'ITEM_UNDO' and pid in p_inv:
                    if p_inv[pid]: p_inv[pid].pop()

                elif etype == 'CHAMPION_KILL':
                    killer, victim = event.get('killerId'), event.get('victimId')
                    if killer in p_stats:
                        p_stats[killer]['k'] += 1
                        objs[player_map[killer]['team_id']]['tk'] += 1
                    if victim in p_stats: p_stats[victim]['d'] += 1
                    for aid in event.get('assistingParticipantIds', []):
                        if aid in p_stats: p_stats[aid]['a'] += 1

                elif etype == 'BUILDING_KILL':
                    tid = event.get('teamId')
                    if tid in objs:
                        if event['buildingType'] == 'TOWER_BUILDING': objs[tid]['t'] += 1
                        else: objs[tid]['i'] += 1

                elif etype == 'ELITE_MONSTER_KILL':
                    tid, mtype = event.get('killerTeamId'), event.get('monsterType')
                    stype = event.get('monsterSubType', '')
                    if tid in objs:
                        if mtype == 'DRAGON':
                            objs[tid]['dt'] += 1
                            for key, s in [('df','FIRE'), ('dw','WATER'), ('de','EARTH'), ('da','AIR'), ('dc','CHEMTECH'), ('dx','HEXTECH')]:
                                if s in stype: objs[tid][key] += 1
                        elif mtype == 'BARON_NASHOR': objs[tid]['b'] += 1
                        elif mtype == 'HORDE': objs[tid]['v'] += 1
                        elif mtype == 'RIFTHERALD': objs[tid]['h'] += 1

            if frame_idx > 0 and frame_idx % 5 == 0:
                p_frames = frame['participantFrames']
                t_gold = {
                    100: sum(f['totalGold'] for p,f in p_frames.items() if player_map[int(p)]['team_id']==100),
                    200: sum(f['totalGold'] for p,f in p_frames.items() if player_map[int(p)]['team_id']==200)
                }

                for pid_str, p_frame in p_frames.items():
                    pid = int(pid_str)
                    p_info = player_map[pid]
                    tid, opp_tid = p_info['team_id'], (200 if p_info['team_id'] == 100 else 100)

                    opp_frame = next((f for opid, f in p_frames.items() 
                                     if player_map[int(opid)]['team_id'] == opp_tid 
                                     and player_map[int(opid)]['role'] == p_info['role']), p_frame)

                    inv = (p_inv[pid] + [0]*7)[:7]
                    
                    self.cursor.execute("""
                        INSERT INTO intervals (
                            match_id, player_id, minute, current_gold, total_gold, cs, jungle_cs, xp, level,
                            kills, deaths, assists, team_kills, team_towers, team_inhibitors,
                            team_dragons, team_barons, team_void_grubs, team_heralds,
                            team_dragons_fire, team_dragons_water, team_dragons_earth,
                            team_dragons_air, team_dragons_chemtech, team_dragons_hextech,
                            item_0, item_1, item_2, item_3, item_4, item_5, item_6,
                            gold_diff, xp_diff, team_gold_diff
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        match_id, p_info['db_id'], frame_idx,
                        p_frame.get('currentGold',0), p_frame.get('totalGold',0),
                        p_frame.get('minionsKilled',0), p_frame.get('jungleMinionsKilled',0),
                        p_frame.get('xp',0), p_frame.get('level',0),
                        p_stats[pid]['k'], p_stats[pid]['d'], p_stats[pid]['a'],
                        objs[tid]['tk'], objs[tid]['t'], objs[tid]['i'],
                        objs[tid]['dt'], objs[tid]['b'], objs[tid]['v'], objs[tid]['h'],
                        objs[tid]['df'], objs[tid]['dw'], objs[tid]['de'],
                        objs[tid]['da'], objs[tid]['dc'], objs[tid]['dx'],
                        *inv,
                        p_frame.get('totalGold',0) - opp_frame.get('totalGold',0),
                        p_frame.get('xp',0) - opp_frame.get('xp',0),
                        t_gold[tid] - t_gold[opp_tid]
                    ))

def run_collection(api, db, name, tag, count):
    print(f"Looking up {name}#{tag}...")
    acc = api.req(f'https://{ROUTING_REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}')
    if not acc: return

    match_ids = api.req(f'https://{ROUTING_REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{acc["puuid"]}/ids?count={count}&queue=420')
    if not match_ids: return

    for m_id in match_ids:
        db.cursor.execute("SELECT 1 FROM matches WHERE match_id = %s", (m_id,))
        if db.cursor.fetchone(): continue

        print(f"Processing {m_id}...")
        m_data = api.req(f'https://{ROUTING_REGION}.api.riotgames.com/lol/match/v5/matches/{m_id}')
        t_data = api.req(f'https://{ROUTING_REGION}.api.riotgames.com/lol/match/v5/matches/{m_id}/timeline')
        
        if not m_data or not t_data: continue
        info = m_data['info']
        
        # Guard against aborted games
        if info.get('endOfGameResult') == 'Abort_Unxpected':
            print("Skipping aborted match.")
            continue

        teams = {t['teamId']: t for t in info['teams']}
        if teams.get(100) is None or teams.get(200) is None:
            print("Skipping match with incomplete team data.")
            continue
        else:
            blue, red = teams[100], teams[200]

            # Rank lookup
            first_p = info['participants'][0]
            rank_data = api.req(f"https://{REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{first_p['puuid']}")
            solo = next((q for q in rank_data if q['queueType'] == 'RANKED_SOLO_5x5'), None) if rank_data else None
            avg_rank = solo['tier'] if solo else "UNRANKED"

            db.cursor.execute("""
                    INSERT INTO matches (match_id, game_duration, patch_version, winning_team, game_date, 
                    game_version, game_mode, queue_id, region, average_rank, blue_bans, red_bans)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    m_id, info['gameDuration'], info['gameVersion'].split('.')[0],
                    100 if blue['win'] else 200, datetime.fromtimestamp(info['gameCreation']/1000),
                    info['gameVersion'], info['gameMode'], info['queueId'], REGION, avg_rank,
                    ",".join(str(b['championId']) for b in blue.get('bans', [])),
                    ",".join(str(b['championId']) for b in red.get('bans', []))
                ))

                
            p_map = {}
            for p in info['participants']:
                db.cursor.execute("""
                        INSERT INTO players (match_id, participant_id, summoner_name, team_id, champion, role, individual_position)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """, (m_id, p['participantId'], p.get('riotIdGameName','Unknown'), p['teamId'], 
                        p['championName'], p['teamPosition'], p.get('individualPosition')))
                    
                p_map[p['participantId']] = {
                        'db_id': db.cursor.lastrowid,
                    'team_id': p['teamId'],
                        'role': p['teamPosition']
                    }

            db.insert_intervals(m_id, p_map, t_data)
            db.conn.commit() # Save everything for this match
            print(f"Match {m_id} saved.")

    

# --- Main Execution ---
if __name__ == "__main__":
    api = RiotAPIClient(RIOT_API_KEY)
    db = DatabaseManager(db_config)

    with open('summoner_names.txt', 'r', encoding='utf-8') as file:
        for line in file:
            if '#' in line:
                name, tag = line.strip().rsplit('#', 1)
                run_collection(api, db, name, tag, 10)
                time.sleep(15) # Short cooldown between summoners


    db.cursor.close()
    db.conn.close()