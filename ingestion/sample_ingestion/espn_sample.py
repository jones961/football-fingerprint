import soccerdata as sd

espn = sd.ESPN(leagues="ENG-Premier League", seasons="2024/2025")
schedule = espn.read_schedule()

arsenal_games = schedule[
    (schedule['home_team'] == 'Arsenal') |
    (schedule['away_team'] == 'Arsenal')
]

first_arsenal_id = int(arsenal_games['game_id'].iloc[0])
print(f"Match id: {first_arsenal_id}")

lineups = espn.read_lineup(match_id=first_arsenal_id)

print(f"\nShape: {lineups.shape}")
print(f"\nData types:\n{lineups.dtypes}")
print(f"\nNull counts:\n{lineups.isnull().sum()}")
print(f"\nUnique positions:\n{lineups['position'].unique()}")
print(f"\nFormation place values:\n{lineups['formation_place'].unique()}")
print(f"\nsub_in values:\n{lineups['sub_in'].unique()}")
print(f"\nsub_out values:\n{lineups['sub_out'].unique()}")
print(f"\nSample rows:\n{lineups.head(10)}")