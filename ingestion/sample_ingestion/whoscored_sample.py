import soccerdata as sd

ws = sd.WhoScored(leagues="ENG-Premier League", seasons="2024/2025")
schedule = ws.read_schedule()

arsenal_games = schedule[
    (schedule['home_team'] == 'Arsenal') |
    (schedule['away_team'] == 'Arsenal')
]

print(f"Arsenal games found: {len(arsenal_games)}")

first_arsenal_id = int(arsenal_games['game_id'].iloc[0])
print(f"\nPulling events for match_id: {first_arsenal_id}")

events = ws.read_events(match_id=first_arsenal_id)

print(f"\nShape: {events.shape}")
print(f"\nData types:\n{events.dtypes}")
print(f"\nNull counts:\n{events.isnull().sum()}")
print(f"\nAction types:\n{events['type'].value_counts()}")
print(f"\nPeriod values:\n{events['period'].unique()}")
print(f"\nis_shot values:\n{events['is_shot'].unique()}")
print(f"\nis_goal values:\n{events['is_goal'].unique()}")
print(f"\nSample qualifiers:\n{events['qualifiers'].iloc[5]}")
print(f"\nSample rows:\n{events.head(10)}")