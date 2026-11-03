"""Convert a Zoom transcript (.vtt) to one line per speaker turn.

Output format: "[hh:mm] Speaker: text". Consecutive cues of the same
speaker go into one line, with the time of the first cue.

Usage: python3 vtt2txt.py transcript.vtt > transcript.txt
"""

import re
import sys

TIME = re.compile(r"^(\d{2}):(\d{2}):\d{2}\.\d{3} -->")
SPEAKER = re.compile(r"^([^:]{1,60}): (.*)$")


def turns(lines):
    stamp, speaker, words = None, None, []
    cue_stamp = None
    for raw in lines:
        line = raw.strip()
        match = TIME.match(line)
        if match:
            cue_stamp = f"{match[1]}:{match[2]}"
            continue
        said = SPEAKER.match(line)
        if not said:
            continue
        if said[1] != speaker:
            if speaker:
                yield stamp, speaker, " ".join(words)
            stamp, speaker, words = cue_stamp, said[1], []
        words.append(said[2])
    if speaker:
        yield stamp, speaker, " ".join(words)


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as vtt:
        for stamp, speaker, text in turns(vtt):
            print(f"[{stamp}] {speaker}: {text}")
