import json
import bisect
import datetime
from dataclasses import dataclass, field
from typing import Optional

import trueskill

__all__ = ['SKILL_MEAN', 'SKILL_STDEV', 'SKILL_GROUP_NAMES', 'Match', 'Player',
           'SkillHistory', 'RoundRow', 'GameStateRow',
           'skill_groups', 'skill_group_name', 'setup_trueskill']

SKILL_MEAN = 1000.0
SKILL_STDEV = SKILL_MEAN / 4.0
BETA = SKILL_STDEV * 2.0
TAU = SKILL_STDEV / 100.0

SKILL_GROUP_SPACING = SKILL_STDEV * 0.5
SKILL_GROUP_NAMES = [
  'Cardboard I',
  'Cardboard II',
  'Cardboard III',
  'Cardboard IV',
  'Plastic I',
  'Plastic II',
  'Plastic III',
  'Plastic Elite',
  'Legendary Wood',
  'Garb Salad',
  'Master Garbian',
  'Master Garbian Elite',
  'Low-Key Dirty',
]
SPECIAL_SKILL_GROUP_NAMES = [
  'Mild Sauce',
  'Soft Taco',
  'Crunchy Taco',
  'Crunchy Taco Supreme',
  'Doritos Locos Taco',
  'Triple Layer Nachos',
  'Nachos Supreme',
  'Nachos Bell Grande',
  'Cheesy Gordita Crunch',
  'Chalupa Supreme',
  'Crunchwrap Supreme',
  'Crunchwrap Supreme Combo',
  'Triplelupa',
]
SKILL_GROUP_CUTOFFS = (float('-inf'),) + tuple(
  SKILL_GROUP_SPACING * (i + 1)
  for i in range(len(SKILL_GROUP_NAMES))
)


def skill_groups():
  return zip(SKILL_GROUP_CUTOFFS, SKILL_GROUP_NAMES)


def skill_group_name(skill_group_index, special_name=False):
  return (SPECIAL_SKILL_GROUP_NAMES
          if special_name
          else SKILL_GROUP_NAMES)[skill_group_index]


def setup_trueskill():
  # TODO: move away from global env

  trueskill.setup(mu=SKILL_MEAN, sigma=SKILL_STDEV, beta=BETA, tau=TAU,
                  draw_probability=0.0)


def find_skill_group(mmr: float) -> int:
  index = bisect.bisect(SKILL_GROUP_CUTOFFS, mmr)
  return index - 1


@dataclass(slots=True, eq=False)
class Player:
  player_id: int
  steam_name: str
  skill_mean: float = field(repr=False)
  skill_stdev: float = field(repr=False)
  impact_rating: float
  skill: trueskill.Rating = field(init=False, repr=False)
  mmr: int = field(init=False)
  skill_group_index: int = field(init=False, repr=False)

  def __post_init__(self):
    self.player_id = int(self.player_id)
    self.skill = trueskill.Rating(self.skill_mean, self.skill_stdev)
    self.mmr = int(self.skill.mu - self.skill.sigma * 2)
    self.skill_group_index = find_skill_group(self.mmr)

  def __lt__(self, other):
    return self.player_id < other.player_id

  def __eq__(self, other):
    return self.player_id == other.player_id

  def __hash__(self):
    return self.player_id

  def __repr__(self):
    return f'<Player "{self.steam_name}">'

  def to_message(self):
    from proto import common_pb2
    return common_pb2.Player(
      player_id=self.player_id,
      steam_name=self.steam_name,
      skill=common_pb2.SkillInfo(
        mmr=float(self.mmr),
        skill_group=skill_group_name(self.skill_group_index),
      ),
    )


@dataclass(slots=True)
class SkillHistory:
  round_id: int
  player_id: int
  skill: trueskill.Rating


@dataclass(slots=True)
class RoundRow:
  round_id: int
  created_at: datetime.datetime
  season_id: int
  winner: int
  loser: int
  mvp: Optional[int]


class GameStateRow:
  game_state_id: int
  round_phase: str
  map_name: str
  map_phase: str
  win_team: str
  timestamp: int
  allplayers: dict
  previous_allplayers: dict

  def __init__(self, game_state_id: int, round_phase: str, map_name: str,
               map_phase: str, win_team: str, timestamp: int, allplayers: str,
               previous_allplayers: Optional[str]):
    self.game_state_id = game_state_id
    self.round_phase = round_phase
    self.map_name = map_name
    self.map_phase = map_phase
    self.win_team = win_team
    self.timestamp = timestamp
    self.allplayers = json.loads(allplayers)
    self.previous_allplayers = {} if previous_allplayers is None \
      else json.loads(previous_allplayers)


@dataclass(slots=True)
class Match:
  team1: list
  team2: list
  quality: float
  p_win: float = field(repr=False)
  team1_win_probability: float = field(init=False)
  team2_win_probability: float = field(init=False)

  def __post_init__(self):
    self.team1_win_probability = round(self.p_win, 2)
    self.team2_win_probability = round(1.0 - self.p_win, 2)

  def __eq__(self, other):
    return self.team1 == other.team1 \
      and self.team2 == other.team2
