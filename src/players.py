from abc import ABC
from pygame.sprite import Sprite
from pygame.sprite import Group
from consts import PlayerAction, PlayerState, PlayerType
from src.consts import PlayerDirection


class Player(Sprite, ABC):

    @property
    def action(self) -> PlayerAction:
        return self._action

    @action.setter
    def action(self, value: PlayerAction) -> None:
        self._action = value

    @property
    def direction(self) -> PlayerDirection:
        return self._direction

    @direction.setter
    def direction(self, value: PlayerDirection) -> None:
        self._direction = value

    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, value: str):
        self._name = value.strip()
        
    @property
    def position(self) -> tuple:
        return self._position
    
    @position.setter
    def position(self, value: tuple):
        self._position = value.strip()

    @property
    def type(self) -> PlayerType:
        return self._type
    
    @type.setter
    def type(self, value: PlayerType):
        self._type = value

    def __init__(self, player_type: PlayerType, name: str, position: tuple, *groups: Group):
        super().__init__(*groups)
        self.action = PlayerAction.STAND
        self.direction = PlayerDirection.DOWN
        self.name = name
        self.position = position
        self.type = player_type


class Human(Player):

    def __init__(self, name: str, position: tuple, *groups: Group):
        super().__init__(PlayerType.HUMAN, name, position, *groups)