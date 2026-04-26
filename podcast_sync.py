"""
podcast_sync.py — Download latest podcast episodes and drop them into iTunes

─────────────────────────────────────────────
FIRST TIME SETUP
─────────────────────────────────────────────
1. Set your iTunes auto-add folder:
     python podcast_sync.py --set-itunes-path "C:\\Users\\YOU\\Music\\iTunes\\iTunes Media\\Automatically Add to iTunes"

2. Add a podcast by RSS URL:
     python podcast_sync.py --add https://feeds.megaphone.fm/MKBHD2879194966

3. Optionally set a download day so it only grabs new episodes on that day:
     python podcast_sync.py --set-day Waveform friday

4. Run manually or schedule with Windows Task Scheduler:
     python podcast_sync.py

─────────────────────────────────────────────
ALL COMMANDS
─────────────────────────────────────────────
  python podcast_sync.py                        Download all due podcasts
  python podcast_sync.py --list                 Show latest episode info (no download)
  python podcast_sync.py --list-podcasts        Show all tracked podcasts + their settings
  python podcast_sync.py --podcast NAME         Download one podcast by name
  python podcast_sync.py --force                Download even if already grabbed this episode
  python podcast_sync.py --add URL              Add a new podcast by RSS URL
  python podcast_sync.py --remove NAME          Remove a podcast from tracking
  python podcast_sync.py --set-day NAME DAY     Set scheduled day (mon/tue/wed/thu/fri/sat/sun/any)
  python podcast_sync.py --set-itunes-path PATH Update the iTunes auto-add folder path
"""

import urllib.request
import xml.etree.ElementTree as ET
import os
import sys
import json
import re
import argparse
from datetime import datetime


SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "podcasts.json")        # podcast list + iTunes path
STATE_FILE  = os.path.join(SCRIPT_DIR, "podcast_state.json")   # tracks downloaded episodes

DAY_NAMES   = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_DISPLAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def load_config():
    """Load podcasts.json, creating a blank one if it doesn't exist yet."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "itunes_auto_add": "",
        "podcasts": []
    }

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"  [saved] {CONFIG_FILE}")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def sanitize_filename(name):
    """Strip characters Windows won't allow in filenames."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def day_str_to_int(day_str):
    """Convert 'friday' / 'fri' / '4' to a 0-6 int. Returns None for 'any'."""
    s = day_str.lower().strip()
    if s in ("any", "none", "always"):
        return None
    for i, name in enumerate(DAY_NAMES):
        if s.startswith(name):
            return i
    if s.isdigit():
        val = int(s)
        if 0 <= val <= 6:
            return val
    raise ValueError(f"Unknown day '{day_str}'. Use mon/tue/wed/thu/fri/sat/sun or 'any'.")


def day_int_to_str(day):
    if day is None:
        return "any"
    return DAY_DISPLAY[day]


def fetch_feed(rss_url):
    """
    Fetch and parse an RSS feed.
    Returns (channel_title, latest_episode_dict).
    episode dict has keys: title, url, pub_date, guid
    """
    headers = {"User-Agent": "Mozilla/5.0 (podcast-sync-script)"}
    req = urllib.request.Request(rss_url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()

    root    = ET.fromstring(data)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("No <channel> found in RSS feed.")

    ch_title_el   = channel.find("title")
    channel_title = ch_title_el.text.strip() if ch_title_el is not None and ch_title_el.text else "Unknown Podcast"

    item = channel.find("item")
    if item is None:
        return channel_title, None

    def text(tag):
        el = item.find(tag)
        return el.text.strip() if el is not None and el.text else ""

    enclosure = item.find("enclosure")
    audio_url = enclosure.get("url") if enclosure is not None else None
    if not audio_url:
        return channel_title, None

    guid = text("guid") or audio_url

    return channel_title, {
        "title":    text("title"),
        "url":      audio_url,
        "pub_date": text("pubDate"),
        "guid":     guid,
    }


def download_episode(episode, dest_folder, podcast_name):
    """Download episode audio to dest_folder. Returns saved path or None."""
    date_str   = datetime.now().strftime("%Y-%m-%d")
    safe_title = sanitize_filename(episode["title"])[:80]
    filename   = f"{podcast_name} - {date_str} - {safe_title}.mp3"
    dest_path  = os.path.join(dest_folder, filename)

    if os.path.exists(dest_path):
        print(f"  [skip] File already exists: {filename}")
        return dest_path

    print(f"  [↓] Downloading: {filename}")
    headers = {"User-Agent": "Mozilla/5.0 (podcast-sync-script)"}
    req     = urllib.request.Request(episode["url"], headers=headers)

    with urllib.request.urlopen(req, timeout=120) as resp:
        total    = resp.headers.get("Content-Length")
        total_mb = f"{int(total)/1024/1024:.1f} MB" if total else "unknown size"
        print(f"      Size: {total_mb}")
        with open(dest_path, "wb") as out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)

    print(f"  [✓] Saved to: {dest_path}")
    return dest_path

def cmd_set_itunes_path(path):
    config = load_config()
    path   = path.strip().strip('"')
    config["itunes_auto_add"] = path
    save_config(config)
    print(f"  iTunes auto-add path set to:\n    {path}")


def cmd_add(rss_url):
    config = load_config()

    for p in config["podcasts"]:
        if p["rss"] == rss_url:
            print(f"  [!] Already tracking: {p['name']} ({rss_url})")
            return

    print(f"  Fetching feed to get podcast name...")
    try:
        channel_title, episode = fetch_feed(rss_url)
    except Exception as e:
        print(f"  [error] Could not fetch RSS: {e}")
        return

    entry = {
        "name": channel_title,
        "rss":  rss_url,
        "day":  None,
    }
    config["podcasts"].append(entry)
    save_config(config)

    print(f"  [+] Added: {channel_title}")
    if episode:
        print(f"      Latest episode: {episode['title']}")
    print(f"      Download day: any (use --set-day \"{channel_title}\" fri to schedule)")


def cmd_remove(name):
    config = load_config()
    before = len(config["podcasts"])
    config["podcasts"] = [p for p in config["podcasts"] if p["name"].lower() != name.lower()]
    if len(config["podcasts"]) == before:
        print(f"  [!] No podcast named '{name}' found. Use --list-podcasts to see names.")
        return
    save_config(config)
    print(f"  [-] Removed: {name}")


def cmd_set_day(name, day_str):
    config = load_config()
    try:
        day_int = day_str_to_int(day_str)
    except ValueError as e:
        print(f"  [!] {e}")
        return

    for p in config["podcasts"]:
        if p["name"].lower() == name.lower():
            p["day"] = day_int
            save_config(config)
            print(f"  [✓] '{p['name']}' will now download on: {day_int_to_str(day_int)}")
            return

    print(f"  [!] No podcast named '{name}' found. Use --list-podcasts to see names.")


def cmd_list_podcasts():
    config   = load_config()
    podcasts = config.get("podcasts", [])
    itunes   = config.get("itunes_auto_add") or "(not set)"

    print(f"\n  iTunes auto-add path : {itunes}")
    print(f"  Config file          : {CONFIG_FILE}\n")

    if not podcasts:
        print("  No podcasts tracked yet. Use --add <rss_url> to add one.")
        return

    print(f"  {'#':<4} {'NAME':<35} {'DAY':<8} RSS")
    print(f"  {'─'*4} {'─'*35} {'─'*8} {'─'*40}")
    for i, p in enumerate(podcasts, 1):
        print(f"  {i:<4} {p['name']:<35} {day_int_to_str(p.get('day')):<8} {p['rss']}")


def cmd_download(filter_name=None, list_only=False, force=False):
    config   = load_config()
    state    = load_state()
    podcasts = config.get("podcasts", [])
    itunes   = config.get("itunes_auto_add", "")
    today    = datetime.now().weekday()

    if not podcasts:
        print("  No podcasts configured. Use --add <rss_url> to add one.")
        return

    if filter_name:
        podcasts = [p for p in podcasts if p["name"].lower() == filter_name.lower()]
        if not podcasts:
            print(f"  [!] No podcast named '{filter_name}'. Use --list-podcasts to see names.")
            return

    if not list_only:
        if not itunes:
            print("  [!] iTunes auto-add path is not set.")
            print("      Run: python podcast_sync.py --set-itunes-path \"C:\\...\\Automatically Add to iTunes\"")
            return
        if not os.path.isdir(itunes):
            print(f"  [!] iTunes auto-add folder not found:\n    {itunes}")
            print("      Update it with: python podcast_sync.py --set-itunes-path \"...\"")
            return

    for podcast in podcasts:
        name = podcast["name"]
        rss  = podcast["rss"]
        day  = podcast.get("day")

        print(f"\n{'─'*50}")
        print(f"  Podcast: {name}")

        if not list_only and day is not None and today != day and not force:
            print(f"  [skip] Scheduled for {day_int_to_str(day)} only. "
                  f"Today is {DAY_DISPLAY[today]}. Use --force to override.")
            continue

        try:
            _, episode = fetch_feed(rss)
        except Exception as e:
            print(f"  [error] Could not fetch RSS: {e}")
            continue

        if episode is None:
            print(f"  [error] No episode found in feed.")
            continue

        print(f"  Title:    {episode['title']}")
        print(f"  Released: {episode['pub_date']}")
        print(f"  URL:      {episode['url'][:72]}...")

        if list_only:
            continue

        if not force and state.get(name) == episode["guid"]:
            print(f"  [skip] Already downloaded this episode. Use --force to re-download.")
            continue

        path = download_episode(episode, itunes, name)
        if path:
            state[name] = episode["guid"]
            save_state(state)
            print(f"  iTunes will import it automatically next time it's open.")

    print(f"\n{'─'*50}")
    if not list_only:
        print("  Done. Connect your iPod and sync in iTunes!")

def main():
    parser = argparse.ArgumentParser(
        description="iTunes podcast downloader for iPod Classic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--list",          action="store_true", help="Show latest episode info without downloading.")
    parser.add_argument("--list-podcasts", action="store_true", help="Show all tracked podcasts and their settings.")
    parser.add_argument("--podcast",       metavar="NAME",      help="Only process one podcast by name.")
    parser.add_argument("--force",         action="store_true", help="Download even if already grabbed this episode.")
    parser.add_argument("--add",           metavar="RSS_URL",   help="Add a new podcast by its RSS feed URL.")
    parser.add_argument("--remove",        metavar="NAME",      help="Stop tracking a podcast.")
    parser.add_argument("--set-day",       nargs=2, metavar=("NAME", "DAY"),
                        help="Set scheduled download day for a podcast (mon-sun or 'any').")
    parser.add_argument("--set-itunes-path", metavar="PATH",    help="Set the iTunes auto-add folder path.")

    args = parser.parse_args()

    if args.set_itunes_path:
        cmd_set_itunes_path(args.set_itunes_path)
    elif args.add:
        cmd_add(args.add)
    elif args.remove:
        cmd_remove(args.remove)
    elif args.set_day:
        cmd_set_day(args.set_day[0], args.set_day[1])
    elif args.list_podcasts:
        cmd_list_podcasts()
    else:
        cmd_download(
            filter_name=args.podcast,
            list_only=args.list,
            force=args.force,
        )


if __name__ == "__main__":
    main()
