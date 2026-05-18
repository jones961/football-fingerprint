import soccerdata as sd

understat = sd.Understat(leagues="ENG-Premier League", seasons="2024/2025")

player_season = understat.read_player_season_stats()

print(f"Columns: {player_season.columns.tolist()}")

arsenal_players = player_season.xs('Arsenal', level='team')

print(f"\nShape: {arsenal_players.shape}")
print(f"\nData types:\n{arsenal_players.dtypes}")
print(f"\nNull counts:\n{arsenal_players.isnull().sum()}")
print(f"\nSample rows:\n{arsenal_players.head(10)}")