#!/usr/bin/env python3
"""
AirPlay Metadata Bridge for Shairport Sync
Reads metadata from the shairport-sync pipe and outputs JSON state + artwork
"""

import os
import sys
import json
import time
import struct
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Configuration
PIPE_PATH = "/tmp/shairport-sync-metadata"
STATE_FILE = "/home/admin/wallclock/airplay_now_playing.json"
ARTWORK_FILE = "/home/admin/wallclock/airplay_artwork.jpg"
STALE_TIMEOUT = 10  # seconds before marking as inactive

# Current state
state = {
    "active": False,
    "title": "",
    "artist": "",
    "album": "",
    "has_artwork": False,
    "source": "",
    "updated_at": None
}

last_update = 0

def write_state_atomic(data):
    """Write state file atomically using temp file + rename"""
    global last_update
    data["updated_at"] = datetime.now().isoformat()
    
    state_path = Path(STATE_FILE)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temp file then rename (atomic on POSIX)
    temp_path = state_path.with_suffix('.tmp')
    with open(temp_path, 'w') as f:
        json.dump(data, f, indent=2)
    shutil.move(str(temp_path), str(state_path))
    last_update = time.time()

def save_artwork(data):
    """Save artwork to file"""
    artwork_path = Path(ARTWORK_FILE)
    artwork_path.parent.mkdir(parents=True, exist_ok=True)
    
    temp_path = artwork_path.with_suffix('.tmp')
    with open(temp_path, 'wb') as f:
        f.write(data)
    shutil.move(str(temp_path), str(artwork_path))
    state["has_artwork"] = True

def clear_artwork():
    """Remove artwork file"""
    try:
        Path(ARTWORK_FILE).unlink(missing_ok=True)
    except:
        pass
    state["has_artwork"] = False

def decode_metadata_item(type_code, code, data):
    """Decode a metadata item from shairport-sync"""
    global state
    
    # Type codes: 'core' for basic metadata, 'ssnc' for shairport-sync specific
    type_str = type_code.decode('ascii', errors='ignore')
    code_str = code.decode('ascii', errors='ignore')
    
    try:
        if type_str == 'core':
            if code_str == 'asal':  # Album
                state["album"] = data.decode('utf-8', errors='ignore')
            elif code_str == 'asar':  # Artist
                state["artist"] = data.decode('utf-8', errors='ignore')
            elif code_str == 'minm':  # Title/Name
                state["title"] = data.decode('utf-8', errors='ignore')
                
        elif type_str == 'ssnc':
            if code_str == 'PICT':  # Picture/Artwork
                if len(data) > 100:  # Sanity check - artwork should be substantial
                    save_artwork(data)
            elif code_str == 'snua':  # Source name/user agent
                state["source"] = data.decode('utf-8', errors='ignore')
            elif code_str == 'pbeg':  # Playback begin
                state["active"] = True
                clear_artwork()  # Clear old artwork on new track
            elif code_str == 'pend':  # Playback end
                state["active"] = False
                state["title"] = ""
                state["artist"] = ""
                state["album"] = ""
                clear_artwork()
            elif code_str == 'prsm':  # Playback resume
                state["active"] = True
            elif code_str == 'pfls':  # Playback flush (pause/stop)
                pass  # Don't clear state on pause
                
    except Exception as e:
        print(f"Error decoding {type_str}/{code_str}: {e}", file=sys.stderr)

def read_metadata_pipe():
    """Read and parse metadata from the shairport-sync pipe"""
    global state, last_update
    
    print(f"Opening metadata pipe: {PIPE_PATH}")
    
    while True:
        try:
            # Open pipe (blocks until writer connects)
            with open(PIPE_PATH, 'rb') as pipe:
                print("Pipe connected, reading metadata...")
                
                while True:
                    # Read header: type (4 bytes) + code (4 bytes) + length (4 bytes)
                    header = pipe.read(12)
                    if len(header) < 12:
                        print("Pipe closed, reconnecting...")
                        break
                    
                    type_code = header[0:4]
                    code = header[4:8]
                    length = struct.unpack('>I', header[8:12])[0]
                    
                    # Read data
                    data = b''
                    if length > 0:
                        data = pipe.read(length)
                    
                    # Decode and update state
                    decode_metadata_item(type_code, code, data)
                    
                    # Write state if we have meaningful data
                    if state["title"] or state["active"]:
                        write_state_atomic(state)
                        
        except FileNotFoundError:
            print(f"Pipe {PIPE_PATH} not found, waiting...")
            time.sleep(2)
        except Exception as e:
            print(f"Error reading pipe: {e}", file=sys.stderr)
            time.sleep(1)
        
        # Check for stale state
        if last_update > 0 and (time.time() - last_update) > STALE_TIMEOUT:
            if state["active"]:
                state["active"] = False
                write_state_atomic(state)

def main():
    print("AirPlay Metadata Bridge starting...")
    
    # Initialize state file
    state["active"] = False
    write_state_atomic(state)
    clear_artwork()
    
    # Start reading
    read_metadata_pipe()

if __name__ == "__main__":
    main()

