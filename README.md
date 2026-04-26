# iTunes-Podcast-Sync

A Python script that downloads the latest episode of your favorite podcasts and drops them into iTunes automatically for syncing to an iPod.

## Disclamer

This python script was vibecoded using Claude Sonnet 4.6. Leaving this here just in case some people are wondering if AI had any hand in developing this script.

## Requirements

- Python 3
- iTunes (Tested on 12.10.11.2, but should work on 10.7 and above)
- Windows (Tested on 11 25H2, but should work on Windows 7-10)
- iPod that can support podcasts (Tested on iPod Classic 7th Generation on 2.0.4)

## Setup

**1. Set your "Automatically Add to iTunes" folder:**
```
python podcast_sync.py --set-itunes-path "C:\Users\YOU\Music\iTunes\iTunes Media\Automatically Add to iTunes"
```

**2. Add a podcast by RSS URL:**
```
python podcast_sync.py --add https://feeds.megaphone.fm/MKBHD2879194966
```

**3. Optionally schedule it to a specific day:**
```
python podcast_sync.py --set-day "Waveform: The MKBHD Podcast" fri
```

**4. Run it manually or set up Windows Task Scheduler to run it automatically.**

## All Commands

| Command | Description |
|---|---|
| `python podcast_sync.py` | Download all due podcasts |
| `--list` | Show latest episode info without downloading |
| `--list-podcasts` | Show all tracked podcasts and their settings |
| `--podcast NAME` | Download one specific podcast by name |
| `--force` | Re-download even if already grabbed this episode |
| `--add URL` | Add a new podcast by RSS feed URL |
| `--remove NAME` | Stop tracking a podcast |
| `--set-day NAME DAY` | Set scheduled day (mon/tue/wed/thu/fri/sat/sun/any) |
| `--set-itunes-path PATH` | Update the iTunes auto-add folder path |

## Notes
I don't know if this should be explicitly mentioned but you are allowed to fork this or repost this repository as long as you give credit and don't make any money off of this.
