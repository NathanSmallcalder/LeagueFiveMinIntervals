-- ============================================
-- REFINED LEAGUE OF LEGENDS SCHEMA (v2.0)
-- ============================================
CREATE DATABASE IF NOT EXISTS LeagueStatsInterval;
USE LeagueStatsInterval;

-- 1. Matches: Added metadata for better filtering
CREATE TABLE matches (
    match_id VARCHAR(50) PRIMARY KEY,
    game_duration INT, 
    patch_version VARCHAR(20),
    winning_team INT, 
    game_date DATETIME,
    game_version VARCHAR(25),
    game_mode VARCHAR(50), 
    queue_id INT, -- More reliable than string names
    region VARCHAR(10),
    average_rank VARCHAR(20),
    -- Bans stored as CSV or individual columns is fine; columns are faster for queries
    blue_bans VARCHAR(255), -- Storing as "Champ1,Champ2..." or keep your 5-column format
    red_bans VARCHAR(255),
    INDEX idx_matches_patch (patch_version),
    INDEX idx_matches_date (game_date)
) ENGINE=InnoDB;

-- 2. Players: Simplified and updated for 2024/2025
CREATE TABLE players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id VARCHAR(50),
    participant_id INT, -- The 1-10 ID from the API
    summoner_name VARCHAR(100),
    team_id INT, 
    champion VARCHAR(50),
    role VARCHAR(20), -- TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY
    individual_position VARCHAR(20),
    FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE,
    INDEX idx_player_lookup (match_id, participant_id)
) ENGINE=InnoDB;

-- 3. Intervals: Optimized for 5-minute snapshots
CREATE TABLE intervals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id VARCHAR(50),
    player_id INT, -- References our internal players.id
    minute INT,
    
    -- Player Performance
    current_gold INT,
    total_gold INT,
    cs INT,
    jungle_cs INT,
    xp INT,
    level INT,
    kills INT,
    deaths INT,
    assists INT,
    
    -- Items (Stored as IDs for efficiency, join with Data Dragon later)
    item_0 INT, item_1 INT, item_2 INT, item_3 INT, item_4 INT, item_5 INT, item_6 INT,
    team_kills INT, -- Team kills at this minute
    -- Team Objective Snapshots (Cumulative at this minute)
    team_inhibitors INT,
    team_towers INT,
    team_dragons_fire INT,
    team_dragons_water INT,
    team_dragons_earth INT,
    team_dragons_air INT,
    team_dragons_chemtech INT,
    team_dragons_hextech INT,
    team_dragons INT,
    team_barons INT,
    team_void_grubs INT, -- Added for modern patches
    team_heralds INT,

    -- Calculated Differentials (Pre-computed for ML/Data Science)
    gold_diff INT, -- Relative to laane opponent
    xp_diff INT,   -- Relative to lane opponent
    team_gold_diff INT, -- Relative to enemy team total
    
    FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    UNIQUE KEY unique_player_interval (player_id, minute)
) ENGINE=InnoDB;