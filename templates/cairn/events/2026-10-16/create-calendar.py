"""Create and check the calendar download from the inspected Google event."""
import datetime as dt
import json
from pathlib import Path
import runpy
from zoneinfo import ZoneInfo

folder = Path(__file__).resolve().parent
helper = runpy.run_path(str(folder.parent.parent / "prepare-event.py"))
event = json.loads((folder / "event.json").read_text(encoding="utf-8"))["cairn"]
calendar = helper["calendar"](event).decode("utf-8")
source = "https://calendar.google.com/calendar/event?action=TEMPLATE&tmeid=XzZnb2s4Y2hsOGNwazJiYTY2NTJqNmI5azg4czMyYmExNmdwajRiOWc2NTMzNGQxbTZrbzNlZGhwNmcgN2JhMGU0YmUzY2YzOWU0MWQ1ZmIxNDI1NTY3NWI3MGNlZWE4YjM1YzRkM2RiY2UyNzE1YWQ0ZGE3NTBiZmZiZEBn&tmsrc=7ba0e4be3cf39e41d5fb14255675b70ceea8b35c4d3dbce2715ad4da750bffbd%40group.calendar.google.com"
extra = helper["fold"]("URL:" + source) + "\r\n"
extra += "BEGIN:VALARM\r\nACTION:DISPLAY\r\nTRIGGER:-PT15M\r\nDESCRIPTION:CAIRN lunchtime reading group starts in 15 minutes\r\nEND:VALARM\r\n"
calendar = calendar.replace("END:VEVENT\r\n", extra + "END:VEVENT\r\n")
output = folder / "cairn-lunchtime-reading-group-2026-10-16.ics"
output.write_bytes(calendar.encode("utf-8"))

# Check the physical encoding and unfold properties before comparing times.
raw = output.read_bytes()
assert raw.endswith(b"END:VCALENDAR\r\n")
assert b"\n" not in raw.replace(b"\r\n", b"")
assert all(len(line) <= 75 for line in raw.split(b"\r\n"))
unfolded = raw.decode("utf-8").replace("\r\n ", "")
properties = {}
stack = []
for line in unfolded.split("\r\n"):
    if not line:
        continue
    key, value = line.split(":", 1)
    if key == "BEGIN":
        stack.append(value)
    elif key == "END":
        assert stack.pop() == value
    elif stack == ["VCALENDAR", "VEVENT"]:
        assert key not in properties, key
        properties[key] = value
assert not stack
assert properties["SUMMARY"] == event["event_title"]
assert properties["LOCATION"] == event["zoom_url"]
assert properties["UID"] == event["uid"]
assert properties["URL"] == source
zone = ZoneInfo("Australia/Sydney")
for attribute, key in (("start", "DTSTART"), ("end", "DTEND")):
    utc = dt.datetime.strptime(properties[key], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    assert utc.astimezone(zone).isoformat() == event[attribute]
assert dt.datetime.fromisoformat(event["start"]).strftime("%A") == "Friday"
assert "TRIGGER:-PT15M\r\n" in unfolded
print(f"Created and verified {output.name}: Friday 16 October 2026, 12:30–13:30 Australia/Sydney; Zoom and 15-minute reminder included.")
