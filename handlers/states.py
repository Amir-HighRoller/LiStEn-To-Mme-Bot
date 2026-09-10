
from aiogram.fsm.state import State, StatesGroup


class AudioExtractionState(StatesGroup):
    waiting_for_video = State()
