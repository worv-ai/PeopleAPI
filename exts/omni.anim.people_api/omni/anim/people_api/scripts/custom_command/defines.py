from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath

import omni.client


class CustomCommandTemplate(Enum):
    NONE = "None"
    TIMING = "Timing"  # Command lasts for given seconds
    # Command will go to the given object and play anim for given seconds
    TIMING_TO_OBJECT = "TimingToObject"
    # Command that blends an animation into default GoTo (with a filter joint)
    GOTO_BLEND = "GoToBlend"


@dataclass
class CustomCommand:
    anim_path: str
    # Attributes below are read from anim USD
    # - General:
    name: str  # Name of the command
    template: CustomCommandTemplate  # Which template it uses
    # Animation Clip settings:
    start_time: float = 0
    end_time: float = 0
    loop: bool = True
    backwards: bool = False
    # - Randomization:
    min_random_time: float = field(default=-1)
    max_random_time: float = field(default=-1)
    interact_object_filter: str = field(default=None)
    # - GoToBlend only:
    filter_joint: str = field(default=None)


def get_anim_prim_name(anim_path):
    url = omni.client.break_url(anim_path)
    name = (PurePosixPath(url.path).name).replace(".", "_").replace("-", "_")
    return name
