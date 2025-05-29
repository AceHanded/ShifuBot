def parse_duration(duration: str) -> int:
    split_duration = duration.split(":")
    if not all(part.isdigit() for part in split_duration): return 0

    if len(split_duration) == 3:
        h = int(split_duration[0])
        m = int(split_duration[1])
        s = int(split_duration[2])
        return h * 3600 + m * 60 + s
    elif len(split_duration) == 2:
        m = int(split_duration[0])
        s = int(split_duration[1])
        return m * 60 + s
    else:
        return int(split_duration[0])
