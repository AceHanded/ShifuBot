def parse_duration(duration: str | None, reference: int | None = None) -> int | None:
    if duration is None: return None

    split_duration = duration.split(":")
    if not all(part.isdigit() for part in split_duration): return 0

    h, m, s = [0] * (3 - len(split_duration)) + [int(part) for part in split_duration]
    parsed_duration = h * 3600 + m * 60 + s
    if (reference): return min(parsed_duration, reference)

    return parsed_duration

def format_duration(duration: int | None, can_be_live: bool = True) -> str | None:
    if duration is None: return "??:??"
    if duration == 0: return "Live" if can_be_live else "00:00"

    h, remainder = divmod(duration, 3600)
    m, s = divmod(remainder, 60)

    return (f"{h:02}:" if h else "") + f"{m:02}:{s:02}"
