"""Validate CAIRN event attributes and create an RFC 5545 .ics calendar file.

No network calls, email sending, external services, or credentials are used.
"""
import argparse
import datetime as dt
import json
import pathlib
import urllib.parse
import uuid
from zoneinfo import ZoneInfo


def event_times(event):
    zone = ZoneInfo(event.get("timezone") or "Australia/Sydney")
    values = []
    for key in ("start", "end"):
        value = dt.datetime.fromisoformat(event[key].replace("Z", "+00:00"))
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{key} requires an explicit UTC offset, e.g. +11:00")
        local = value.astimezone(zone)
        if value.utcoffset() != local.utcoffset():
            raise ValueError(f"{key}'s offset does not match {zone.key} on that date")
        values.append(value)
    if values[1].astimezone(dt.timezone.utc) <= values[0].astimezone(dt.timezone.utc):
        raise ValueError("end must be later than start")
    for key in ("zoom_url", "calendar_ics_url"):
        url = event.get(key, "")
        if url and (urllib.parse.urlsplit(url).scheme != "https" or not urllib.parse.urlsplit(url).netloc or "\n" in url or "\r" in url):
            raise ValueError(f"{key} must be an HTTPS URL without newlines")
    return values


def text(value):
    return str(value).replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def fold(line):
    parts, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            parts.append(current)
            current = " "
        current += char
    parts.append(current)
    return "\r\n".join(parts)


def calendar(event):
    start, end = event_times(event)
    title = (event.get("calendar_title") or "CAIRN: Lunchtime Reading Group").strip()
    if not title:
        raise ValueError("calendar_title must not be empty")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = event.setdefault("uid", str(uuid.uuid4()) + "@cairn.org.au")
    description = event.get("calendar_description", "")
    if event.get("event_title"):
        description = "Reading topic: " + event["event_title"] + "\n" + description
    if event.get("zoom_url"):
        description += "\n\nJoin Zoom: " + event["zoom_url"]
    if event.get("zoom_meeting_id"):
        description += "\nMeeting ID: " + event["zoom_meeting_id"]
    if event.get("zoom_passcode"):
        description += "\nPasscode: " + event["zoom_passcode"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CAIRN//Reading Group//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT", "UID:" + text(uid),
             "DTSTAMP:" + stamp, "DTSTART:" + start.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "DTEND:" + end.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
             "SUMMARY:" + text(title), "DESCRIPTION:" + text(description.strip()),
             "LOCATION:" + text(event.get("zoom_url") or "Online via Zoom"),
             "TRANSP:OPAQUE", "END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(fold(line) for line in lines) + "\r\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=pathlib.Path, help="JSON attributes containing a cairn object")
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("event-output"))
    args = parser.parse_args()
    attributes = json.loads(args.input.read_text(encoding="utf-8-sig"))
    ics = calendar(attributes["cairn"])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "cairn-reading-group.ics").write_bytes(ics)
    (args.output / "campaign-attributes.json").write_text(json.dumps(attributes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Created calendar file and validated attributes in " + str(args.output))


if __name__ == "__main__":
    main()
