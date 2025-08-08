from enum import IntEnum, StrEnum

class EmbedColor(IntEnum):
    BLUE = 0x25649E
    DARK_RED = 0x800000
    GREEN = 0x608000
    PURPLE = 0x76259E
    RED = 0xe03a3a
    YELLOW = 0xdb9142

class Emoji(StrEnum):
    DEFAULT = ":grey_question:"
    FILE = "<:file:1366159986597691392>"
    BANDCAMP = "<:bandcamp:1403153520273653972>"
    SOUNDCLOUD = "<:soundcloud:1267269257423618060>"
    SPOTIFY = "<:spotify:1267269271390519376>"
    YOUTUBE_MUSIC = "<:youtube_music:1366160008059944960>"
    YOUTUBE = "<:youtube:1267269233772073153>"
    BACK = "<:goback:1142844613003067402>"
    LOOP = "<:loopy:1196862829752500265>"
    PAUSE = "<:playpause:1086408066490183700>"
    REMOVE = "<:remove:1197082264924852325>"
    SKIP = "<:skip:1086405128787067001>"
    VOLUME_MIN = "<:volume_mute:1143513586967257190>"
    VOLUME_DOWN = "<:volume_down:1143513584505192520>"
    VOLUME_MID = "<:volume_mid:1143514064023212174>"
    VOLUME_UP = "<:volume_up:1143513588623999087>"
    VOLUME_MAX = "<:volume:1142886748200910959>"

class TerminalColor(StrEnum):
    END = "\x1b[0m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    CYAN = "\x1b[36m"
