import datetime as dt
import pandas as pd
import panel as pn

from io import StringIO

pn.extension(notifications=True)


class BoardGamePicker:

    def __init__(self):

        self.DEFAULT_MIN_PLAYERS = 1
        self.DEFAULT_MAX_PLAYERS = 1
        self.DEFAULT_DURATION = 0
        self.DEFAULT_COUNT = 0
        self.OLDER_GAMES = "Pick games I haven't played in a while"
        self.UNUSED_GAMES = "Pick games I haven't played much"
        self.BASE_WEIGHT_MODIFIER = 0.2

        self.board_games = pd.DataFrame(
            columns=["Name", "Minimum Players", "Maximum Players", "Longest Duration", "Last Played", "Times Played"])
        #  This is a workaround to get the date formatting right
        self.board_games.loc[len(self.board_games)] = ["Example Game", 1, 4, 30, dt.date.today(), 0]

        editors = {"Name": "textarea",
                   "Minimum Players": {'type': 'number', 'min': 1},
                   "Maximum Players": {'type': 'number', 'min': 1},
                   "Longest Duration": {'type': 'number', 'min': 1},
                   "Last Played": "date",
                   "Times Played": {'type': 'number', 'min': 1}
                   }

        self.games_table = pn.widgets.Tabulator(self.board_games, buttons={"delete": "<i class=\"fa fa-trash\"></i>"},
                                                editors=editors, hidden_columns=["index"])
        self.games_table.on_click(self.__delete_row)
        self.games_table.on_edit(self.__edit_table)

        self.from_file_widget = pn.widgets.FileInput(name="Choose File", accept=".csv")
        self.file_ingest_button = pn.widgets.Button(name="Fill Table From File", button_type="primary")
        self.file_ingest_button.on_click(self.__ingest_file)

        self.game_name_widget = pn.widgets.TextInput(name="Board Game Name", placeholder="Name")
        self.min_players_widget = pn.widgets.IntInput(name="Minimum Players", start=self.DEFAULT_MIN_PLAYERS)
        self.max_players_widget = pn.widgets.IntInput(name="Maximum Players", start=self.DEFAULT_MAX_PLAYERS)
        self.duration_widget = pn.widgets.IntInput(name="Longest Duration (Minutes)", start=self.DEFAULT_DURATION)
        self.date_widget = pn.widgets.DatePicker(name="Last Played", end=dt.date.today())
        self.count_widget = pn.widgets.IntInput(name="Times Played", start=self.DEFAULT_COUNT)
        self.submit_button = pn.widgets.Button(name="Add to your games", button_type="primary")
        self.submit_button.on_click(self.__add_row)

        self.download_games_widget = pn.widgets.FileDownload(callback=self.__get_csv, filename="my_games.csv")

        self.preferences_widget = pn.widgets.CheckBoxGroup(options=[self.OLDER_GAMES, self.UNUSED_GAMES])
        self.player_quantity_widget = pn.widgets.IntInput(name="Number of Players", start=self.DEFAULT_MIN_PLAYERS)
        self.available_time_widget = pn.widgets.IntInput(name="Available Time", start=self.DEFAULT_DURATION)
        self.pick_game_button = pn.widgets.Button(name="Recommend Games", button_type="primary")
        self.pick_game_button.on_click(self.__pick_game)

        self.suggestions_quantity_widget = pn.widgets.EditableIntSlider(name="How many suggestion?", start=1, end=10,
                                                                        step=1, value=3)
        self.suggested_games_table = pn.widgets.Tabulator(pd.DataFrame(columns=["Suggested Games", "Longest Duration"]),
                                                          hidden_columns=["index"])

    def __ingest_file(self, event):
        if self.from_file_widget.value is not None:
            new_games = pd.read_csv(StringIO(self.from_file_widget.value.decode("utf-8")), delimiter='\t',
                                    parse_dates=["Last Played"])
            new_games["Last Played"] = new_games["Last Played"].apply(lambda d: d.date())
            self.board_games = pd.concat([self.board_games, new_games], ignore_index=True)

            self.board_games = self.board_games.drop(
                self.board_games[self.board_games["Name"] == "Example Game"].index).reset_index(drop=True)

            self.games_table.value = self.board_games

    def __delete_row(self, event):
        if event.column == "delete":
            self.board_games = self.board_games.drop(event.row).reset_index(drop=True)
            self.games_table.value = self.board_games

    def __edit_table(self, event):
        if event.old != event.value:
            self.board_games.at[event.row, event.column] = event.value

    def __add_row(self, event):
        self.board_games.loc[len(self.board_games)] = [
            self.game_name_widget.value,
            self.min_players_widget.value,
            self.max_players_widget.value,
            self.duration_widget.value,
            self.date_widget.value,
            self.count_widget.value
        ]
        self.game_name_widget.value = ""
        self.min_players_widget.value = self.DEFAULT_MIN_PLAYERS
        self.max_players_widget.value = self.DEFAULT_MAX_PLAYERS
        self.duration_widget.value = self.DEFAULT_DURATION
        self.count_widget.value = self.DEFAULT_COUNT

        self.board_games = self.board_games.drop(
            self.board_games[self.board_games["Name"] == "Example Game"].index).reset_index(drop=True)

        self.games_table.value = self.board_games

    def __get_csv(self):
        string_io = StringIO()
        self.board_games.to_csv(string_io, index=False, sep='\t')
        string_io.seek(0)
        return string_io

    def __pick_game(self, event):
        possible_games = self.board_games.loc[
            (self.board_games["Minimum Players"] <= int(self.player_quantity_widget.value))
            & (int(self.player_quantity_widget.value) <= self.board_games["Maximum Players"])
            & (int(self.available_time_widget.value) >= self.board_games["Longest Duration"])]

        if len(possible_games) == 0:
            pn.state.notifications.error("No games match your parameters", duration=0)
            self.suggested_games_table.value = pd.DataFrame(columns=["Suggested Games", "Longest Duration"])

        else:

            weights = [self.BASE_WEIGHT_MODIFIER / len(possible_games["Name"]) for _ in possible_games["Name"]]

            if self.OLDER_GAMES in self.preferences_widget.value:
                days_apart = [d.days for d in (dt.date.today() - possible_games["Last Played"])]
                older_game_weights = [days / max(sum(days_apart), 1) for days in days_apart]
                weights = [weight + new_weight for weight, new_weight in zip(weights, older_game_weights)]

            if self.UNUSED_GAMES in self.preferences_widget.value:
                times_played_inverse = [(max(possible_games["Times Played"]) - times_played) /
                                        max(1, sum(possible_games["Times Played"]))
                                        for times_played in possible_games["Times Played"]]
                normalized_times_played = [time_played / max(sum(times_played_inverse), 1)
                                           for time_played in times_played_inverse]
                weights = [weight + new_weight for weight, new_weight in zip(weights, normalized_times_played)]

            weights = [weight / sum(weights) for weight in weights]
            print(weights)

            self.suggested_games_table.value = possible_games.sample(
                n=min(self.suggestions_quantity_widget.value, len(possible_games)),
                replace=False, weights=weights)[["Name", "Longest Duration"]].rename(columns={"Name": "Suggested Game"})

    def get_dashboard(self):
        return (
            pn.Column(
                pn.Row(
                    self.from_file_widget,
                    self.file_ingest_button
                ),
                pn.Row(
                    self.game_name_widget,
                    self.min_players_widget,
                    self.max_players_widget,
                    self.duration_widget,
                    self.date_widget,
                    self.count_widget
                ),
                pn.Row(
                    self.submit_button
                ),
                pn.Row(
                    self.games_table
                ),
                pn.Row(
                    self.download_games_widget
                ),
                pn.Row(
                    self.suggestions_quantity_widget,
                    self.preferences_widget,
                    self.player_quantity_widget,
                    self.available_time_widget,
                    self.pick_game_button
                ),
                pn.Row(
                    self.suggested_games_table
                )
            )
        )

    def get_template(self):
        return pn.template.FastListTemplate(
            title="Board Game Picker",
            sidebar=[self.from_file_widget,
                     self.file_ingest_button,
                     self.game_name_widget,
                     self.min_players_widget,
                     self.max_players_widget,
                     self.duration_widget,
                     self.date_widget,
                     self.count_widget,
                     self.submit_button,
                     self.download_games_widget
                     ],
            main=[pn.Row(self.games_table,
                         pn.Column(self.suggestions_quantity_widget,
                                   self.preferences_widget,
                                   self.player_quantity_widget,
                                   self.available_time_widget,
                                   self.pick_game_button,
                                   self.suggested_games_table)
                         )]
        )


board_game_picker = BoardGamePicker()
template = board_game_picker.get_template()
template.servable()

# uncomment this to view the widgets in a jupyter notebook
# board_game_picker.get_dashboard()
