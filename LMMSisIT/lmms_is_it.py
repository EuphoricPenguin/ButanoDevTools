#!/usr/bin/env python3
"""
LMMS MMP/MMPZ to Impulse Tracker (IT) Converter

Converts LMMS project files (.mmp, .mmpz) to Impulse Tracker format (.it).

Based on the conversion strategy outlined in program_plan.md and the
LMMS Save Format Specification.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import struct
import io
import zlib
import math
import os
import subprocess
import tempfile
import shutil
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from xml.etree import ElementTree as ET

# Try to import numpy and soundfile for sample rendering
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False


# =============================================================================
# Global tracking for rendering modes
# =============================================================================

# List of (track_name, mode_string) tuples populated during rendering
RENDERING_MODES_USED = []


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class LMMSNote:
    """Represents a single note in an LMMS MIDI clip."""
    pos: int          # absolute position in ticks
    len: int          # duration in ticks
    key: int          # MIDI key 0-127
    vol: int          # 0-200
    pan: int          # -100 to 100


@dataclass
class LMMSMidiClip:
    """Represents a MIDI clip in LMMS."""
    pos: int          # clip start position in ticks
    length: int       # clip length in ticks
    muted: bool
    notes: List[LMMSNote]


@dataclass
class MixerChannel:
    """Represents a mixer channel in LMMS."""
    num: int
    name: str
    volume: float       # 0.0-2.0
    muted: bool
    sends: Dict[int, float]  # {target_channel: amount}


@dataclass
class LMMSInstrumentTrack:
    """Represents an instrument track in LMMS."""
    name: str
    muted: bool
    solo: bool
    instrument_name: str    # e.g. "tripleoscillator", "AudioFileProcessor"
    instrument_elem: ET.Element  # XML element for rendering
    vol: float              # 0-200
    pan: float              # -100 to 100
    pitch: float            # cents
    basenote: int           # MIDI key (69 = A4)
    mixch: int              # mixer channel assignment
    use_master_pitch: bool
    clips: List[LMMSMidiClip]
    fx_chain: Optional[ET.Element]


@dataclass
class RenderedSample:
    """Represents a rendered audio sample."""
    name: str               # max 26 chars for IT
    filename: str           # max 12 chars (DOS 8.3)
    data: 'np.ndarray'      # mono or stereo float32 audio
    sample_rate: int       # e.g. 44100
    base_note: int         # MIDI key this was recorded at
    loop_start: int        # in sample frames, 0 if no loop
    loop_end: int          # in sample frames, 0 if no loop
    is_looped: bool
    is_stereo: bool


@dataclass
class ITEvent:
    """Represents a note event in IT format."""
    row: int
    note: int           # IT note value (0-119, or 255=note off, 254=note cut)
    instrument: int     # 1-99
    volume: int         # 0-64 (or 255=no volume)
    effect: int         # effect command
    effect_param: int   # effect parameter
    panning: int        # 0-64 or -1 for none


@dataclass
class ITChannel:
    """Represents an IT channel with its events."""
    instrument_index: int   # which IT instrument this channel serves
    events: Dict[int, ITEvent]  # {row: ITEvent}
    default_pan: int        # 0-64


@dataclass
class ITGainMapping:
    """How to distribute LMMS gain across IT's volume controls."""
    global_volume: int      # 0-128, set once in header
    mixing_volume: int      # 0-128, set once in header
    inst_global_vol: int    # 0-128, per instrument
    sample_global_vol: int  # 0-64, per sample
    channel_vol: int        # 0-64, per channel
    note_vol: int           # 0-64, per note event


# =============================================================================
# MMP/MMPZ Parsing
# =============================================================================

def load_mmp(filepath: str) -> ET.Element:
    """Load and parse an MMP or MMPZ file."""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    if filepath.lower().endswith('.mmpz'):
        # Qt's qCompress prepends a 4-byte big-endian uncompressed size
        expected_size = struct.unpack('>I', data[:4])[0]
        raw_xml = zlib.decompress(data[4:])
        if len(raw_xml) != expected_size:
            print(f"Warning: Decompressed size mismatch. Expected {expected_size}, got {len(raw_xml)}")
    else:
        raw_xml = data
    
    return ET.fromstring(raw_xml)


def extract_project_globals(root: ET.Element) -> dict:
    """Extract global project parameters from the LMMS project."""
    head = root.find('head')
    if head is None:
        head = ET.Element('head')
    
    timesig_num = int(head.get('timesig_numerator', '4'))
    timesig_den = int(head.get('timesig_denominator', '4'))
    ticks_per_bar = (timesig_num * 48 * 4) // timesig_den
    
    return {
        'bpm': int(head.get('bpm', '140')),
        'timesig_num': timesig_num,
        'timesig_den': timesig_den,
        'master_vol': int(head.get('mastervol', '100')),
        'master_pitch': int(head.get('masterpitch', '0')),
        'ticks_per_bar': ticks_per_bar,
    }


def extract_tracks(root: ET.Element) -> Tuple[List[LMMSInstrumentTrack], Dict[int, MixerChannel]]:
    """Extract all instrument tracks and mixer channels from the project."""
    tracks = []
    mixer_channels = {}
    
    # Extract mixer channels
    mixer = root.find('.//mixer')
    if mixer is not None:
        for mch in mixer.findall('mixerchannel'):
            num = int(mch.get('num', '0'))
            sends = {}
            for send in mch.findall('send'):
                target_ch = int(send.get('channel', '0'))
                amount = float(send.get('amount', '1.0'))
                sends[target_ch] = amount
            mixer_channels[num] = MixerChannel(
                num=num,
                name=mch.get('name', f'Channel {num}'),
                volume=float(mch.get('volume', '1.0')),
                muted=mch.get('muted', '0') == '1',
                sends=sends,
            )
    
    # Ensure master channel exists
    if 0 not in mixer_channels:
        mixer_channels[0] = MixerChannel(0, 'Master', 1.0, False, {})
    
    # Extract instrument tracks
    for track_elem in root.findall('.//trackcontainer/track'):
        track_type = int(track_elem.get('type', '-1'))
        if track_type != 0:  # Only instrument tracks
            continue
        
        it_elem = track_elem.find('instrumenttrack')
        if it_elem is None:
            continue
        
        inst_elem = it_elem.find('instrument')
        inst_name = inst_elem.get('name', '') if inst_elem is not None else ''
        
        clips = []
        for clip_elem in track_elem.findall('midiclip'):
            clip_pos = int(clip_elem.get('pos', '0'))
            clip_muted = clip_elem.get('muted', '0') == '1'
            clip_len = int(clip_elem.get('len', '0'))
            
            notes = []
            for note_elem in clip_elem.findall('note'):
                note_pos = int(note_elem.get('pos', '0'))
                note_len = int(note_elem.get('len', '0'))
                if note_len <= 0:
                    continue  # skip step-sequencer markers
                notes.append(LMMSNote(
                    pos=clip_pos + note_pos,  # absolute position
                    len=note_len,
                    key=int(note_elem.get('key', '69')),
                    vol=int(note_elem.get('vol', '100')),
                    pan=int(note_elem.get('pan', '0')),
                ))
            
            clips.append(LMMSMidiClip(
                pos=clip_pos, length=clip_len,
                muted=clip_muted, notes=notes,
            ))
        
        tracks.append(LMMSInstrumentTrack(
            name=track_elem.get('name', 'Unnamed'),
            muted=track_elem.get('muted', '0') == '1',
            solo=track_elem.get('solo', '0') == '1',
            instrument_name=inst_name,
            instrument_elem=inst_elem,
            vol=float(it_elem.get('vol', '100')),
            pan=float(it_elem.get('pan', '0')),
            pitch=float(it_elem.get('pitch', '0')),
            basenote=int(it_elem.get('basenote', '69')),
            mixch=int(it_elem.get('mixch', '0')),
            use_master_pitch=it_elem.get('usemasterpitch', '1') == '1',
            clips=clips,
            fx_chain=it_elem.find('fxchain'),
        ))
    
    return tracks, mixer_channels


# =============================================================================
# LMMS CLI Rendering Support
# =============================================================================

# Global flag for LMMS availability
LMMS_PATH = None

def find_lmms_executable() -> Optional[str]:
    """Find the LMMS executable on the system."""
    global LMMS_PATH
    
    if LMMS_PATH is not None:
        return LMMS_PATH if LMMS_PATH else None
    
    # Common LMMS executable names and paths
    possible_names = ['lmms', 'lmms.exe', 'LMMS.exe']
    
    # Check PATH
    for name in possible_names:
        path = shutil.which(name)
        if path:
            LMMS_PATH = path
            return path
    
    # Check common installation directories on Windows
    if os.name == 'nt':
        program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
        program_files_x86 = os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        
        possible_paths = [
            os.path.join(program_files, 'LMMS', 'lmms.exe'),
            os.path.join(program_files_x86, 'LMMS', 'lmms.exe'),
            os.path.join(local_appdata, 'Programs', 'LMMS', 'lmms.exe'),
            os.path.join(local_appdata, 'LMMS', 'lmms.exe'),
        ]
        
        for path in possible_paths:
            if os.path.isfile(path):
                LMMS_PATH = path
                return path
    
    # Check common paths on Linux/macOS
    else:
        possible_paths = [
            '/usr/bin/lmms',
            '/usr/local/bin/lmms',
            '/opt/lmms/bin/lmms',
            '/Applications/LMMS.app/Contents/MacOS/lmms',
        ]
        
        for path in possible_paths:
            if os.path.isfile(path):
                LMMS_PATH = path
                return path
    
    LMMS_PATH = ''  # Mark as not found
    return None


def modify_project_for_sample_render(original_root: ET.Element,
                                      track_index: int,
                                      base_note: int,
                                      duration_seconds: float,
                                      project_globals: dict) -> str:
    """
    Modify a copy of the original LMMS project to render a single instrument sample.
    
    Preserves ALL project data (FX chains, mixer routing, effects, etc.) but:
    - Mutes all tracks except the target track
    - Replaces the target track's MIDI clips with a single C4 note
    - Sets timeline to render just the note duration
    
    Args:
        original_root: Parsed XML root of original project
        track_index: Index of the track to render (0-based)
        base_note: MIDI note to render (e.g., 60 = C4)
        duration_seconds: Duration of the note to render
        project_globals: Project timing info
    
    Returns:
        Modified MMP XML string
    """
    import copy
    
    # Deep copy the original project to preserve all data
    root = copy.deepcopy(original_root)
    
    bpm = project_globals['bpm']
    
    # Calculate note length in ticks
    ticks_per_beat = 48
    seconds_per_tick = 60.0 / (bpm * ticks_per_beat)
    note_len_ticks = int(duration_seconds / seconds_per_tick)
    note_len_ticks = max(48, min(192 * 8, note_len_ticks))
    
    # Find the track container
    trackcontainer = root.find('.//trackcontainer')
    if trackcontainer is None:
        # Try alternative path
        trackcontainer = root.find('.//song/trackcontainer')
    
    if trackcontainer is None:
        raise ValueError("Could not find trackcontainer in project")
    
    # Process all instrument tracks
    current_track_idx = 0
    for track_elem in trackcontainer.findall('track'):
        track_type = int(track_elem.get('type', '-1'))
        if track_type != 0:  # Only instrument tracks
            continue
        
        if current_track_idx == track_index:
            # This is the target track - modify its clips
            track_elem.set('muted', '0')  # Unmute
            track_elem.set('solo', '0')   # No solo
            
            # Remove all existing MIDI clips
            for clip in list(track_elem.findall('midiclip')):
                track_elem.remove(clip)
            for clip in list(track_elem.findall('patternclip')):
                track_elem.remove(clip)
            
            # Add a single MIDI clip with one note
            new_clip = ET.SubElement(track_elem, 'midiclip')
            new_clip.set('pos', '0')
            new_clip.set('len', str(note_len_ticks))
            new_clip.set('muted', '0')
            new_clip.set('type', '1')
            
            # Add the single note
            new_note = ET.SubElement(new_clip, 'note')
            new_note.set('pos', '0')
            new_note.set('len', str(note_len_ticks))
            new_note.set('key', str(base_note))
            new_note.set('vol', '100')
            new_note.set('pan', '0')
            
        else:
            # Other tracks - mute them
            track_elem.set('muted', '1')
        
        current_track_idx += 1
    
    # Update timeline to render just the note
    timeline = root.find('.//timeline')
    if timeline is not None:
        timeline.set('loopEnabled', '0')
        timeline.set('loopStart', '0')
        timeline.set('loopEnd', str(note_len_ticks))
        # Clear timeline positions
        for pos in list(timeline.findall('timelinepos')):
            timeline.remove(pos)
        new_pos = ET.SubElement(timeline, 'timelinepos')
        new_pos.set('pos', str(note_len_ticks))
    
    # Unmute all mixer channels (preserve the mixer state)
    mixer = root.find('.//mixer')
    if mixer is not None:
        for mch in mixer.findall('mixerchannel'):
            # Keep existing mixer settings, just ensure not muted
            mch.set('muted', '0')
    
    # Convert to string
    return ET.tostring(root, encoding='unicode')


def create_minimal_mmp_for_rendering(track: LMMSInstrumentTrack, 
                                      project_globals: dict,
                                      base_note: int,
                                      duration_seconds: float = 3.0,
                                      original_root: ET.Element = None,
                                      track_index: int = None) -> str:
    """
    Create an MMP project for rendering a single instrument sample.
    
    If original_root and track_index are provided, preserves the entire
    project (FX chains, mixer routing, effects) and just replaces note data.
    
    Args:
        track: The instrument track to render
        project_globals: Project global settings
        base_note: MIDI note to render
        duration_seconds: Duration of the note
        original_root: Original project XML root (to preserve FX chains)
        track_index: Index of the track in the original project
    
    Returns:
        MMP XML string
    """
    # If we have the original project, preserve it and just modify note data
    if original_root is not None and track_index is not None:
        return modify_project_for_sample_render(
            original_root, track_index, base_note, duration_seconds, project_globals
        )
    
    # Fallback: create minimal project (loses FX chains, mixer routing)
    # This is the old behavior - kept for backward compatibility
    bpm = project_globals['bpm']
    ticks_per_bar = project_globals['ticks_per_bar']
    
    ticks_per_beat = 48
    seconds_per_tick = 60.0 / (bpm * ticks_per_beat)
    note_len_ticks = int(duration_seconds / seconds_per_tick)
    note_len_ticks = max(48, min(192 * 8, note_len_ticks))
    
    inst_xml = ''
    if track.instrument_elem is not None:
        inst_xml = ET.tostring(track.instrument_elem, encoding='unicode')
    
    mmp_template = f'''<?xml version="1.0"?>
<!DOCTYPE lmms-project>
<lmms-project version="27" type="song" creator="LMMS" creatorversion="1.3.0">
  <head bpm="{bpm}" timesig_numerator="{project_globals['timesig_num']}" 
        timesig_denominator="{project_globals['timesig_den']}"
        mastervol="100" masterpitch="0"/>
  <song>
    <trackcontainer>
      <track type="0" name="render_track" muted="0" solo="0">
        <instrumenttrack vol="100" pan="0" pitch="0" basenote="{base_note}" 
                         usemasterpitch="1" mixch="0">
          {inst_xml}
        </instrumenttrack>
        <midiclip pos="0" len="{note_len_ticks}" muted="0" type="1">
          <note pos="0" len="{note_len_ticks}" key="{base_note}" vol="100" pan="0"/>
        </midiclip>
      </track>
    </trackcontainer>
    <mixer>
      <mixerchannel num="0" name="Master" volume="1.0" muted="0"/>
    </mixer>
    <timeline loopEnabled="0" loopStart="0" loopEnd="{note_len_ticks}">
      <timelinepos pos="0"/>
    </timeline>
  </song>
</lmms-project>'''
    
    return mmp_template


def render_via_lmms_cli(track: LMMSInstrumentTrack, project_globals: dict,
                        base_note: int, sample_rate: int = 44100,
                        duration: float = 3.0, temp_dir: str = None,
                        original_root: ET.Element = None,
                        track_index: int = None) -> Optional['np.ndarray']:
    """
    Render an instrument using LMMS CLI.
    
    Preserves FX chains and mixer routing if original_root is provided.
    
    Args:
        track: The instrument track to render
        project_globals: Project timing info
        base_note: MIDI note to render
        sample_rate: Target sample rate
        duration: Duration in seconds
        temp_dir: Temp directory for files
        original_root: Original project XML (preserves FX chains if provided)
        track_index: Index of track in original project
    
    Returns:
        Audio data as numpy array, or None if failed
    """
    if not HAS_NUMPY or not HAS_SOUNDFILE:
        return None
    
    lmms_exe = find_lmms_executable()
    if not lmms_exe:
        return None
    
    # Create temporary files
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    
    temp_mmp = os.path.join(temp_dir, f'lmms_render_{id(track)}.mmp')
    temp_wav = os.path.join(temp_dir, f'lmms_render_{id(track)}.wav')
    
    try:
        # Create MMP - use full project if available to preserve FX chains
        mmp_xml = create_minimal_mmp_for_rendering(
            track, project_globals, base_note, duration,
            original_root=original_root, track_index=track_index
        )
        with open(temp_mmp, 'w', encoding='utf-8') as f:
            f.write(mmp_xml)
        
        # Run LMMS render
        cmd = [
            lmms_exe, 'render', temp_mmp,
            '-o', temp_wav,
            '-f', 'wav',
            '-s', str(sample_rate)
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            timeout=60,  # 60 second timeout
            cwd=temp_dir
        )
        
        if result.returncode != 0:
            print(f"LMMS render failed: {result.stderr.decode('utf-8', errors='replace')}")
            return None
        
        # Read the rendered audio
        if not os.path.exists(temp_wav):
            return None
        
        audio_data, sr = sf.read(temp_wav, dtype='float32')
        
        # Handle stereo - convert to mono if needed for simplicity
        if audio_data.ndim == 2:
            # Keep stereo for now
            pass
        
        # Trim trailing silence
        audio_data = trim_trailing_silence(audio_data, threshold=1e-5)
        
        return audio_data
        
    except subprocess.TimeoutExpired:
        print("LMMS render timed out")
        return None
    except Exception as e:
        print(f"LMMS render error: {e}")
        return None
    finally:
        # Clean up temp files
        try:
            if os.path.exists(temp_mmp):
                os.remove(temp_mmp)
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
        except:
            pass


def trim_trailing_silence(audio: 'np.ndarray', threshold: float = 1e-5) -> 'np.ndarray':
    """Remove trailing silence from audio array."""
    if audio.ndim == 2:
        amplitude = np.max(np.abs(audio), axis=1)
    else:
        amplitude = np.abs(audio)
    
    indices = np.where(amplitude > threshold)[0]
    if len(indices) == 0:
        return audio[:1]  # Return at least 1 sample
    
    last_nonsilent = indices[-1]
    tail = min(1024, len(audio) - last_nonsilent - 1)
    return audio[:last_nonsilent + tail + 1]


# =============================================================================
# Sample Rendering (Simplified - generates simple waveforms)
# =============================================================================

def render_simple_sample(base_note: int, sample_rate: int = 44100, 
                         duration: float = 2.0, wave_type: int = 0) -> 'np.ndarray':
    """Generate a simple waveform sample for basic instruments."""
    if not HAS_NUMPY:
        return None
    
    base_freq = 440.0 * (2.0 ** ((base_note - 69) / 12.0))
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    wave_funcs = {
        0: lambda f, t: np.sin(2 * np.pi * f * t),  # Sine
        1: lambda f, t: 2 * np.abs(2 * ((f * t) % 1) - 1) - 1,  # Triangle
        2: lambda f, t: 2 * ((f * t) % 1) - 1,  # Saw
        3: lambda f, t: np.sign(np.sin(2 * np.pi * f * t)),  # Square
        4: lambda f, t: np.random.uniform(-1, 1, len(t)),  # Noise
    }
    
    wave_func = wave_funcs.get(wave_type, wave_funcs[0])
    output = wave_func(base_freq, t).astype(np.float32)
    
    # Apply simple envelope (attack, decay, sustain, release)
    attack = int(0.01 * sample_rate)
    release = int(0.2 * sample_rate)
    sustain_level = 0.7
    
    # Attack
    if attack > 0:
        output[:attack] *= np.linspace(0, 1, attack)
    
    # Release
    if release > 0 and release < len(output):
        release_start = len(output) - release
        output[release_start:] *= np.linspace(1, 0, release)
    
    return output


def render_triple_oscillator(inst_elem: ET.Element, base_note: int, 
                             sample_rate: int = 44100, duration: float = 2.0) -> 'np.ndarray':
    """Render TripleOscillator instrument to sample."""
    if not HAS_NUMPY:
        return None
    
    to_elem = inst_elem.find('.//TripleOscillator')
    if to_elem is None:
        to_elem = inst_elem.find('.//tripleoscillator')
    if to_elem is None:
        # Fall back to simple sine
        return render_simple_sample(base_note, sample_rate, duration, 0)
    
    base_freq = 440.0 * (2.0 ** ((base_note - 69) / 12.0))
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    output = np.zeros(num_samples, dtype=np.float32)
    
    # Wave functions
    def sine_wave(f, t, ph):
        return np.sin(2 * np.pi * f * t + ph)
    
    def triangle_wave(f, t, ph):
        return 2 * np.abs(2 * ((f * t + ph / (2 * np.pi)) % 1) - 1) - 1
    
    def saw_wave(f, t, ph):
        return 2 * ((f * t + ph / (2 * np.pi)) % 1) - 1
    
    def square_wave(f, t, ph):
        return np.sign(np.sin(2 * np.pi * f * t + ph))
    
    def noise_wave(f, t, ph):
        return np.random.uniform(-1, 1, len(t))
    
    wave_funcs = [sine_wave, triangle_wave, saw_wave, square_wave, noise_wave]
    
    for i in range(3):
        vol = float(to_elem.get(f'vol{i}', '33.33')) / 100.0
        coarse = int(to_elem.get(f'coarse{i}', '0'))
        fine_l = float(to_elem.get(f'finel{i}', '0'))
        fine_r = float(to_elem.get(f'finer{i}', '0'))
        wave_type = int(to_elem.get(f'wavetype{i}', '0'))
        ph_offset = float(to_elem.get(f'phoffset{i}', '0')) * np.pi / 180.0
        
        detune_cents = coarse * 100.0 + (fine_l + fine_r) / 2.0
        freq = base_freq * (2.0 ** (detune_cents / 1200.0))
        
        if wave_type < len(wave_funcs):
            osc_output = wave_funcs[wave_type](freq, t, ph_offset) * vol
        else:
            osc_output = wave_funcs[0](freq, t, ph_offset) * vol
        
        output += osc_output
    
    # Normalize
    peak = np.max(np.abs(output))
    if peak > 0:
        output = output / peak * 0.8  # Leave headroom
    
    # Apply envelope
    attack = int(0.01 * sample_rate)
    release = int(0.3 * sample_rate)
    if attack > 0:
        output[:attack] *= np.linspace(0, 1, attack)
    if release > 0 and release < len(output):
        release_start = len(output) - release
        output[release_start:] *= np.linspace(1, 0, release)
    
    return output


def render_tracks_via_lmms_cli(mmp_path: str, output_dir: str, 
                               sample_rate: int = 44100) -> Dict[str, str]:
    """
    Render all tracks from an LMMS project to separate WAV files.
    
    Uses LMMS rendertracks command to render each instrument track individually.
    Returns a dict mapping track names to their rendered WAV file paths.
    """
    rendered_files = {}
    
    lmms_exe = find_lmms_executable()
    if not lmms_exe:
        print("ERROR: LMMS executable not found. Cannot render tracks.")
        return rendered_files
    
    # Run LMMS rendertracks
    cmd = [
        lmms_exe, 'rendertracks', mmp_path,
        '-o', output_dir,
        '-f', 'wav',
        '-s', str(sample_rate),
        '-b', '16'
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,  # 5 minute timeout for full project
            cwd=output_dir
        )
        
        if result.returncode != 0:
            print(f"LMMS rendertracks failed: {result.stderr.decode('utf-8', errors='replace')}")
            return rendered_files
        
        # Find rendered files - LMMS names them as <tracknum>_<trackname>.wav
        for filename in os.listdir(output_dir):
            if filename.endswith('.wav'):
                # Parse track name from filename (format: N_TrackName.wav)
                parts = filename.split('_', 1)
                if len(parts) == 2:
                    track_name = os.path.splitext(parts[1])[0]
                    rendered_files[track_name] = os.path.join(output_dir, filename)
                else:
                    # Fallback: use whole filename
                    track_name = os.path.splitext(filename)[0]
                    rendered_files[track_name] = os.path.join(output_dir, filename)
        
        print(f"Rendered {len(rendered_files)} tracks via LMMS CLI")
        
    except subprocess.TimeoutExpired:
        print("ERROR: LMMS rendertracks timed out")
    except Exception as e:
        print(f"ERROR: LMMS rendertracks error: {e}")
    
    return rendered_files


def load_rendered_wav(wav_path: str, expected_name: str) -> Optional[RenderedSample]:
    """
    Load a rendered WAV file and create a RenderedSample.
    """
    if not HAS_SOUNDFILE or not HAS_NUMPY:
        return None
    
    try:
        audio_data, sr = sf.read(wav_path, dtype='float32')
        
        # Determine if stereo
        is_stereo = audio_data.ndim == 2
        
        # Trim trailing silence
        audio_data = trim_trailing_silence(audio_data, threshold=1e-5)
        
        # Create DOS-compatible filename
        safe_name = ''.join(c if c.isalnum() else '_' for c in expected_name[:8])
        filename = safe_name.upper()[:8] + '.WAV'
        
        return RenderedSample(
            name=expected_name[:26],
            filename=filename,
            data=audio_data,
            sample_rate=sr,
            base_note=69,  # A4 - standard base note for rendered samples
            loop_start=0,
            loop_end=len(audio_data),
            is_looped=False,
            is_stereo=is_stereo,
        )
        
    except Exception as e:
        print(f"ERROR loading {wav_path}: {e}")
        return None


def render_instrument_sample(track: LMMSInstrumentTrack, project_globals: dict,
                             sample_rate: int = 44100, 
                             use_lmms_cli: bool = True,
                             duration: float = 5.0,
                             render_note: int = 60,
                             original_root: ET.Element = None,
                             track_index: int = None) -> Optional[RenderedSample]:
    """
    Render an instrument track to a sample.
    
    Args:
        track: The instrument track to render
        project_globals: Project global settings (BPM, etc.)
        sample_rate: Target sample rate
        use_lmms_cli: If True, require LMMS CLI for rendering
        duration: Duration in seconds for the sample
        render_note: MIDI note to render (default: 60 = C4/middle C)
        original_root: Original project XML (preserves FX chains if provided)
        track_index: Index of track in original project
    
    Returns:
        RenderedSample or None if rendering failed
    """
    # Require LMMS CLI for rendering
    if not use_lmms_cli or not HAS_SOUNDFILE:
        print(f"  ERROR: '{track.name}' cannot be rendered - LMMS CLI and soundfile required")
        RENDERING_MODES_USED.append((track.name, "FAILED"))
        return None
    
    # Render via LMMS CLI - creates modified MMP with single note, preserving FX chains
    lmms_audio = render_via_lmms_cli(
        track, project_globals, render_note, 
        sample_rate, duration,
        original_root=original_root, track_index=track_index
    )
    
    if lmms_audio is not None:
        is_stereo = lmms_audio.ndim == 2
        RENDERING_MODES_USED.append((track.name, "LMMS CLI"))
        print(f"  Rendered '{track.name}' via LMMS CLI")
    else:
        print(f"  ERROR: Failed to render '{track.name}' via LMMS CLI")
        RENDERING_MODES_USED.append((track.name, "FAILED"))
        return None
    
    # Create DOS-compatible filename
    safe_name = ''.join(c if c.isalnum() else '_' for c in track.name[:8])
    filename = safe_name.upper()[:8] + '.WAV'
    
    return RenderedSample(
        name=track.name[:26],
        filename=filename,
        data=lmms_audio,
        sample_rate=sample_rate,
        base_note=track.basenote,
        loop_start=0,
        loop_end=len(lmms_audio),
        is_looped=False,
        is_stereo=is_stereo,
    )


# =============================================================================
# IT File Writing
# =============================================================================

class ITWriter:
    """Writes IT (Impulse Tracker) module files."""
    
    def __init__(self):
        self.buffer = io.BytesIO()
    
    def write_header(self, song_name: str, num_orders: int, num_instruments: int,
                     num_samples: int, num_patterns: int, global_volume: int,
                     mixing_volume: int, initial_speed: int, initial_tempo: int,
                     channel_pans: List[int] = None, channel_vols: List[int] = None):
        """Write the 192-byte IT file header."""
        self.buffer.seek(0)
        
        # Magic
        self.buffer.write(b'IMPM')
        
        # Song name (26 bytes, null-padded)
        name_bytes = song_name.encode('ascii', errors='replace')[:25]
        self.buffer.write(name_bytes.ljust(26, b'\x00'))
        
        # Pattern row highlight
        self.buffer.write(struct.pack('<BB', 8, 16))
        
        # OrdNum, InsNum, SmpNum, PatNum
        self.buffer.write(struct.pack('<HHHH',
            num_orders, num_instruments, num_samples, num_patterns))
        
        # Cwt/v, Cmwt (created with/compatible with tracker version)
        cwt_v = 0x0214  # IT 2.14
        cmwt = 0x0214
        self.buffer.write(struct.pack('<HH', cwt_v, cmwt))
        
        # Flags
        flags = 0x01  # Stereo
        flags |= 0x02  # Vol0MixOptimizations
        flags |= 0x08  # Linear slides
        flags |= 0x10  # Old Effects
        if num_instruments > 0:
            flags |= 0x04  # Use Instruments
        self.buffer.write(struct.pack('<H', flags))
        
        # Special flags
        special = 0x04  # Row highlights present
        self.buffer.write(struct.pack('<H', special))
        
        # GV, MV, IS, IT, Sep, PWD
        self.buffer.write(struct.pack('<BBBBBB',
            min(128, max(0, global_volume)),
            min(128, max(0, mixing_volume)),
            min(255, max(1, initial_speed)),
            min(255, max(32, initial_tempo)),
            128,  # Pan separation
            0,    # Pitch Wheel Depth
        ))
        
        # Message length and offset (no message)
        self.buffer.write(struct.pack('<HI', 0, 0))
        
        # Reserved
        self.buffer.write(struct.pack('<I', 0))
        
        # Channel Pan (64 bytes)
        if channel_pans is None:
            channel_pans = [32] * 64  # center
        for i in range(64):
            self.buffer.write(struct.pack('B', channel_pans[i] if i < len(channel_pans) else (32 | 128)))
        
        # Channel Volume (64 bytes)
        if channel_vols is None:
            channel_vols = [64] * 64
        for i in range(64):
            self.buffer.write(struct.pack('B', channel_vols[i] if i < len(channel_vols) else 0))
        
        assert self.buffer.tell() == 192, f"Header is {self.buffer.tell()} bytes, expected 192"
    
    def write_orders_and_pointers(self, orders: List[int], num_instruments: int,
                                   num_samples: int, num_patterns: int) -> Tuple[int, int, int]:
        """Write order list and parapointer arrays. Returns offsets for later patching."""
        assert self.buffer.tell() == 192
        
        # Order list
        for order in orders:
            self.buffer.write(struct.pack('B', order))
        
        # Instrument parapointers (placeholders)
        inst_ptr_offset = self.buffer.tell()
        for _ in range(num_instruments):
            self.buffer.write(struct.pack('<I', 0))
        
        # Sample parapointers (placeholders)
        smp_ptr_offset = self.buffer.tell()
        for _ in range(num_samples):
            self.buffer.write(struct.pack('<I', 0))
        
        # Pattern parapointers (placeholders)
        pat_ptr_offset = self.buffer.tell()
        for _ in range(num_patterns):
            self.buffer.write(struct.pack('<I', 0))
        
        return inst_ptr_offset, smp_ptr_offset, pat_ptr_offset
    
    def write_instrument(self, name: str, global_volume: int, default_pan: int,
                         sample_index: int) -> int:
        """Write an IT instrument header. Returns the offset."""
        offset = self.buffer.tell()
        
        # Magic
        self.buffer.write(b'IMPI')
        
        # DOS Filename (12 bytes + null)
        dos_name = name.encode('ascii', errors='replace')[:12]
        self.buffer.write(dos_name.ljust(13, b'\x00'))
        
        # NNA, DCT, DCA
        self.buffer.write(struct.pack('BBB', 0, 0, 0))
        
        # FadeOut
        self.buffer.write(struct.pack('<H', 256))
        
        # PPS, PPC
        self.buffer.write(struct.pack('bB', 0, 60))
        
        # GbV (Global Volume), DfP (Default Pan)
        self.buffer.write(struct.pack('BB', min(128, global_volume), default_pan))
        
        # RV, RP
        self.buffer.write(struct.pack('BB', 0, 0))
        
        # TrkVers, NoS
        self.buffer.write(struct.pack('<HB', 0x0214, 1))
        
        # Reserved
        self.buffer.write(b'\x00')
        
        # Instrument Name (26 bytes)
        inst_name = name.encode('ascii', errors='replace')[:26]
        self.buffer.write(inst_name.ljust(26, b'\x00'))
        
        # IFC, IFR
        self.buffer.write(struct.pack('BB', 0, 0))
        
        # MCh, MPr, MBk
        self.buffer.write(struct.pack('BbH', 0, -1, 0))
        
        # Note-Sample Keyboard Table (240 bytes = 120 entries × 2 bytes)
        for note in range(120):
            self.buffer.write(struct.pack('BB', note, sample_index))
        
        # Volume Envelope
        self._write_envelope(enabled=False)
        
        # Panning Envelope
        self._write_envelope(enabled=False)
        
        # Pitch Envelope
        self._write_envelope(enabled=False)
        
        # Pad to 554 bytes from start
        current = self.buffer.tell()
        expected = offset + 554
        if current < expected:
            self.buffer.write(b'\x00' * (expected - current))
        
        return offset
    
    def _write_envelope(self, enabled: bool = False):
        """Write a blank IT envelope (82 bytes)."""
        flags = 0x01 if enabled else 0x00
        self.buffer.write(struct.pack('B', flags))  # Flags
        self.buffer.write(struct.pack('B', 0))      # Num nodes
        self.buffer.write(struct.pack('B', 0))      # Loop begin
        self.buffer.write(struct.pack('B', 0))      # Loop end
        self.buffer.write(struct.pack('B', 0))      # Sustain begin
        self.buffer.write(struct.pack('B', 0))      # Sustain end
        # 25 node points × 3 bytes each
        self.buffer.write(b'\x00' * 75)
        self.buffer.write(b'\x00')  # padding
    
    def write_sample_header(self, sample: RenderedSample, sample_data_offset: int = 0) -> Tuple[int, int]:
        """Write an IT sample header. Returns (offset, pointer_position)."""
        offset = self.buffer.tell()
        
        # Magic
        self.buffer.write(b'IMPS')
        
        # DOS Filename (12 bytes + null)
        dos_name = sample.filename.encode('ascii', errors='replace')[:12]
        self.buffer.write(dos_name.ljust(13, b'\x00'))
        
        # GvL (Global Volume, 0-64)
        self.buffer.write(struct.pack('B', 64))
        
        # Flags
        smp_flags = 0x01  # Sample present
        smp_flags |= 0x02  # 16-bit
        if sample.is_stereo:
            smp_flags |= 0x04
        if sample.is_looped:
            smp_flags |= 0x10
        self.buffer.write(struct.pack('B', smp_flags))
        
        # Vol (Default Volume, 0-64)
        self.buffer.write(struct.pack('B', 64))
        
        # Sample name (26 bytes)
        smp_name = sample.name.encode('ascii', errors='replace')[:26]
        self.buffer.write(smp_name.ljust(26, b'\x00'))
        
        # Cvt (Convert flags): bit 0 = signed samples
        self.buffer.write(struct.pack('B', 0x01))
        
        # DfP (Default Pan): 0-64, bit 7 = use default pan
        self.buffer.write(struct.pack('B', 32 | 128))
        
        # Length (in samples)
        num_frames = len(sample.data)
        self.buffer.write(struct.pack('<I', num_frames))
        
        # Loop Begin, Loop End
        self.buffer.write(struct.pack('<II', sample.loop_start, sample.loop_end))
        
        # C5Speed (sample rate at C-5 = middle C)
        # Adjust for base note: if sample was recorded at A4 (69),
        # C5Speed = sample_rate * 2^((60 - base_note)/12)
        c5_speed = int(sample.sample_rate * (2.0 ** ((60 - sample.base_note) / 12.0)))
        self.buffer.write(struct.pack('<I', c5_speed))
        
        # Sustain Loop Begin, End
        self.buffer.write(struct.pack('<II', 0, 0))
        
        # SamplePointer (offset to sample data, filled in later)
        sample_ptr_pos = self.buffer.tell()
        self.buffer.write(struct.pack('<I', sample_data_offset))
        
        # ViS, ViD, ViR, ViT (Vibrato)
        self.buffer.write(struct.pack('BBBB', 0, 0, 0, 0))
        
        assert self.buffer.tell() - offset == 80, \
            f"Sample header is {self.buffer.tell() - offset} bytes, expected 80"
        
        return offset, sample_ptr_pos
    
    def write_pattern(self, rows: int, channels: List[ITChannel], 
                      num_channels: int) -> int:
        """Write a packed IT pattern. Returns the file offset."""
        pattern_offset = self.buffer.tell()
        
        # Placeholder for length
        length_pos = self.buffer.tell()
        self.buffer.write(struct.pack('<H', 0))
        self.buffer.write(struct.pack('<H', rows))
        self.buffer.write(b'\x00\x00\x00\x00')  # reserved
        
        data_start = self.buffer.tell()
        
        for row in range(rows):
            for ch_idx in range(min(num_channels, len(channels))):
                ch = channels[ch_idx]
                if row not in ch.events:
                    continue
                
                event = ch.events[row]
                
                # Channel variable with mask flag
                channel_var = (ch_idx + 1) | 0x80
                
                # Mask variable
                mask = 0
                if event.note < 254 or event.note == 255:
                    mask |= 0x01  # Note present
                if event.instrument > 0:
                    mask |= 0x02  # Instrument present
                if event.volume != 255:
                    mask |= 0x04  # Volume present
                if event.effect != 0 or event.effect_param != 0:
                    mask |= 0x08  # Command present
                
                if mask == 0:
                    continue
                
                self.buffer.write(struct.pack('B', channel_var))
                self.buffer.write(struct.pack('B', mask))
                
                if mask & 0x01:  # Note
                    self.buffer.write(struct.pack('B', event.note))
                
                if mask & 0x02:  # Instrument
                    self.buffer.write(struct.pack('B', event.instrument))
                
                if mask & 0x04:  # Volume
                    vol_byte = event.volume
                    if event.panning >= 0 and event.panning != 32:
                        vol_byte = 128 + event.panning  # Panning in volume column
                    self.buffer.write(struct.pack('B', vol_byte))
                
                if mask & 0x08:  # Command
                    self.buffer.write(struct.pack('BB', event.effect, event.effect_param))
            
            # End of row marker
            self.buffer.write(struct.pack('B', 0))
        
        data_end = self.buffer.tell()
        packed_length = data_end - data_start
        
        # Fill in the length
        self.buffer.seek(length_pos)
        self.buffer.write(struct.pack('<H', packed_length))
        self.buffer.seek(data_end)
        
        return pattern_offset
    
    def write_sample_data(self, sample: RenderedSample) -> int:
        """Write raw 16-bit signed sample data. Returns file offset."""
        offset = self.buffer.tell()
        
        audio = sample.data
        
        # Convert float32 [-1, 1] to int16
        if HAS_NUMPY and audio.dtype != np.int16:
            audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        else:
            audio_int16 = audio
        
        if sample.is_stereo and audio_int16.ndim == 2:
            # IT stereo: left channel first, then right channel (NOT interleaved)
            left = audio_int16[:, 0]
            right = audio_int16[:, 1]
            self.buffer.write(left.tobytes())
            self.buffer.write(right.tobytes())
        else:
            if audio_int16.ndim == 2:
                audio_int16 = audio_int16[:, 0]  # Mono mixdown
            self.buffer.write(audio_int16.tobytes())
        
        return offset
    
    def get_buffer(self) -> bytes:
        """Get the complete file buffer."""
        self.buffer.seek(0)
        return self.buffer.read()


# =============================================================================
# Gain and Volume Mapping
# =============================================================================

def compute_it_panning(note: LMMSNote, track: LMMSInstrumentTrack) -> int:
    """Compute IT panning value (0-64, 32=center) from LMMS panning."""
    combined_pan = max(-100, min(100, note.pan + track.pan))
    it_pan = int((combined_pan + 100) / 200.0 * 64.0)
    return max(0, min(64, it_pan))


def distribute_gain(note_vol_lmms: float, track_vol_lmms: float,
                    mixer_vol: float, send_amount: float,
                    master_vol_lmms: float) -> Tuple[ITGainMapping, float]:
    """Distribute total LMMS gain across IT volume controls."""
    # Normalize to linear scale
    note_lin = note_vol_lmms / 100.0
    track_lin = track_vol_lmms / 100.0
    master_lin = master_vol_lmms / 100.0
    
    total_lin = note_lin * track_lin * mixer_vol * send_amount * master_lin
    
    # IT's total gain product maxes at 1.0
    sample_pre_amp = 1.0
    if total_lin > 1.0:
        sample_pre_amp = total_lin
        total_lin = 1.0
    
    # Distribute across IT controls
    master_clamped = min(1.0, master_lin)
    it_global = round(master_clamped * 128)
    
    static_gain = min(1.0, track_lin * mixer_vol * send_amount)
    it_inst_gv = round(static_gain * 128)
    
    note_clamped = min(1.0, note_lin)
    remaining = static_gain if static_gain > 0 else 1.0
    note_clamped = min(1.0, note_clamped * remaining)
    it_note_vol = round(note_clamped * 64)
    
    return ITGainMapping(
        global_volume=min(128, max(0, it_global)),
        mixing_volume=128,
        inst_global_vol=min(128, max(0, it_inst_gv)),
        sample_global_vol=64,
        channel_vol=64,
        note_vol=min(64, max(0, it_note_vol)),
    ), sample_pre_amp


# =============================================================================
# Timing and Channel Allocation
# =============================================================================

def compute_timing_params(project_globals: dict) -> dict:
    """Map LMMS timing to IT speed/tempo."""
    bpm = project_globals['bpm']
    ticks_per_bar = project_globals['ticks_per_bar']
    ticks_per_beat = ticks_per_bar // project_globals['timesig_num']
    
    # Default: 12 rows per beat (each row = 4 LMMS ticks)
    rows_per_beat = 12
    ticks_per_row = ticks_per_beat // rows_per_beat
    
    if ticks_per_row < 1:
        ticks_per_row = 1
        rows_per_beat = ticks_per_beat
    
    # IT timing: Speed * 2.5 / Tempo = row duration in seconds
    # LMMS: ticks_per_row * 60 / (48 * BPM) = row duration in seconds
    # Simplified: Speed = ticks_per_row / 2, Tempo = BPM
    
    it_speed = max(1, ticks_per_row // 2)
    it_tempo = max(32, min(255, bpm))
    
    rows_per_bar = ticks_per_bar // ticks_per_row
    
    return {
        'ticks_per_row': ticks_per_row,
        'rows_per_beat': rows_per_beat,
        'rows_per_bar': rows_per_bar,
        'it_speed': it_speed,
        'it_tempo': it_tempo,
    }


def tick_to_row(tick: int, ticks_per_row: int) -> int:
    """Convert LMMS tick position to IT row index."""
    return tick // ticks_per_row


def allocate_channels(tracks: List[LMMSInstrumentTrack], ticks_per_row: int,
                      mixer_channels: Dict[int, MixerChannel],
                      project_globals: dict) -> List[ITChannel]:
    """Allocate IT channels for all notes across all LMMS tracks."""
    all_channels: List[ITChannel] = []
    
    for track_idx, track in enumerate(tracks):
        if track.muted:
            continue
        
        # Collect all notes from non-muted clips
        all_notes = []
        for clip in track.clips:
            if clip.muted:
                continue
            all_notes.extend(clip.notes)
        
        # Sort by position
        all_notes.sort(key=lambda n: (n.pos, n.key))
        
        # Channels for this instrument
        inst_channels: List[ITChannel] = []
        
        for note in all_notes:
            start_row = tick_to_row(note.pos, ticks_per_row)
            end_row = tick_to_row(note.pos + note.len, ticks_per_row)
            if end_row == start_row:
                end_row = start_row + 1
            
            # Find a free channel
            assigned_channel = None
            for ch in inst_channels:
                is_free = True
                for row in range(start_row, end_row + 1):
                    if row in ch.events:
                        is_free = False
                        break
                if is_free:
                    assigned_channel = ch
                    break
            
            # Allocate new channel if needed
            if assigned_channel is None:
                if len(all_channels) >= 64:
                    continue  # Skip - exceeded 64 channels
                
                assigned_channel = ITChannel(
                    instrument_index=track_idx + 1,
                    events={},
                    default_pan=compute_it_panning(LMMSNote(0, 0, 69, 100, 0), track),
                )
                inst_channels.append(assigned_channel)
                all_channels.append(assigned_channel)
            
            # Compute gain
            gain_map, _ = distribute_gain(
                note.vol, track.vol,
                mixer_channels.get(track.mixch, MixerChannel(0, '', 1.0, False, {})).volume,
                mixer_channels.get(track.mixch, MixerChannel(0, '', 1.0, False, {0: 1.0})).sends.get(0, 1.0),
                project_globals['master_vol'],
            )
            
            # Convert LMMS MIDI key to IT note
            it_note = max(0, min(119, note.key))
            
            # Place note-on
            assigned_channel.events[start_row] = ITEvent(
                row=start_row,
                note=it_note,
                instrument=track_idx + 1,
                volume=gain_map.note_vol,
                effect=0,
                effect_param=0,
                panning=compute_it_panning(note, track),
            )
            
            # Place note-off
            if end_row not in assigned_channel.events:
                assigned_channel.events[end_row] = ITEvent(
                    row=end_row,
                    note=255,  # Note Off
                    instrument=0,
                    volume=255,
                    effect=0,
                    effect_param=0,
                    panning=-1,
                )
    
    return all_channels


# =============================================================================
# Main Conversion Function
# =============================================================================

def convert_mmp_to_it(mmp_path: str, it_path: str, progress_callback=None) -> bool:
    """
    Complete MMP/MMPZ to IT conversion pipeline.
    
    Creates minimal MMP files with single notes (C4) for each instrument,
    renders them via LMMS CLI to get instrument samples, then builds IT file.
    
    Args:
        mmp_path: Path to input .mmp or .mmpz file
        it_path: Path to output .it file
        progress_callback: Optional callback for progress updates
    
    Returns:
        True on success, False on failure
    """
    if not HAS_NUMPY:
        raise ImportError("NumPy is required for audio processing. Install with: pip install numpy")
    
    if not HAS_SOUNDFILE:
        raise ImportError("soundfile is required for reading rendered audio. Install with: pip install soundfile")
    
    # Check for LMMS executable
    lmms_exe = find_lmms_executable()
    if not lmms_exe:
        raise RuntimeError(
            "LMMS executable not found! This converter requires LMMS to be installed.\n"
            "Install LMMS from https://lmms.io/ and ensure it's in your PATH."
        )
    
    # Clear previous rendering mode tracking
    RENDERING_MODES_USED.clear()
    
    # === PHASE 1: Parse ===
    if progress_callback:
        progress_callback("Parsing LMMS project file...")
    
    try:
        root = load_mmp(mmp_path)
    except Exception as e:
        raise ValueError(f"Failed to parse LMMS file: {e}")
    
    project_globals = extract_project_globals(root)
    tracks, mixer_channels = extract_tracks(root)
    
    if not tracks:
        raise ValueError("No instrument tracks found in project")
    
    # Filter to non-muted tracks
    active_tracks = [t for t in tracks if not t.muted]
    if not active_tracks:
        raise ValueError("All tracks are muted - nothing to convert")
    
    # === PHASE 2: Render instrument samples via LMMS CLI ===
    # Each instrument is rendered as a single note (C4 / middle C) to create a sample
    if progress_callback:
        progress_callback(f"Rendering {len(active_tracks)} instrument samples via LMMS CLI...")
    
    rendered_samples: List[RenderedSample] = []
    track_to_sample: Dict[int, int] = {}
    sample_rate = 44100
    sample_duration = 5.0  # 5 second samples
    
    # Create temp directory for rendered files
    temp_dir = tempfile.mkdtemp(prefix='lmms_it_samples_')
    
    try:
        for i, track in enumerate(tracks):
            if track.muted:
                continue
            
            if progress_callback:
                progress_callback(f"Rendering sample {len(rendered_samples)+1}/{len(active_tracks)}: {track.name}")
            
            # Use C4 (middle C = MIDI 60) as the base note for samples
            # This gives a good range for transposition in the IT player
            sample_note = 60  # C4 / middle C
            
            # Render this instrument playing a single note
            # Pass original_root to preserve FX chains and mixer routing
            sample = render_instrument_sample(
                track, project_globals, sample_rate,
                use_lmms_cli=True, duration=sample_duration,
                render_note=sample_note,
                original_root=root,
                track_index=i
            )
            
            if sample:
                # Override base_note to C4 since we rendered at C4
                sample.base_note = sample_note
                rendered_samples.append(sample)
                track_to_sample[i] = len(rendered_samples)
            else:
                print(f"  WARNING: Failed to render sample for '{track.name}'")
    
    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    if not rendered_samples:
        raise ValueError("No samples could be rendered - LMMS CLI may have failed")
    
    # === PHASE 3 & 4: Timing + Channel Allocation ===
    if progress_callback:
        progress_callback("Computing timing and allocating channels...")
    
    timing = compute_timing_params(project_globals)
    ticks_per_row = timing['ticks_per_row']
    
    # Find total length in rows
    max_tick = 0
    for track in tracks:
        for clip in track.clips:
            for note in clip.notes:
                max_tick = max(max_tick, note.pos + note.len)
    
    total_rows = tick_to_row(max_tick, ticks_per_row) + 4
    
    # Allocate channels
    it_channels = allocate_channels(tracks, ticks_per_row, mixer_channels, project_globals)
    num_channels = len(it_channels)
    
    if num_channels == 0:
        raise ValueError("No notes to convert")
    
    if num_channels > 64:
        num_channels = 64
        it_channels = it_channels[:64]
    
    # === PHASE 5: Split into patterns ===
    rows_per_pattern = min(200, timing['rows_per_bar'] * 4)
    num_patterns = math.ceil(total_rows / rows_per_pattern)
    
    if num_patterns > 200:
        rows_per_pattern = min(200, math.ceil(total_rows / 200))
        num_patterns = math.ceil(total_rows / rows_per_pattern)
    
    # Order list
    orders = list(range(num_patterns))
    orders.append(255)  # End marker
    
    # === PHASE 6: Compute gain distribution ===
    gain_map, _ = distribute_gain(100, 100, 1.0, 1.0, project_globals['master_vol'])
    
    # === PHASE 7: Write IT File ===
    if progress_callback:
        progress_callback("Writing IT file...")
    
    writer = ITWriter()
    
    song_name = os.path.splitext(os.path.basename(mmp_path))[0]
    num_instruments = len(rendered_samples)
    num_samples = len(rendered_samples)
    
    # Channel pans
    channel_pans = []
    for i in range(64):
        if i < len(it_channels):
            channel_pans.append(it_channels[i].default_pan)
        else:
            channel_pans.append(32 | 128)  # disabled
    
    writer.write_header(
        song_name=song_name,
        num_orders=len(orders),
        num_instruments=num_instruments,
        num_samples=num_samples,
        num_patterns=num_patterns,
        global_volume=gain_map.global_volume,
        mixing_volume=128,
        initial_speed=timing['it_speed'],
        initial_tempo=timing['it_tempo'],
        channel_pans=channel_pans,
        channel_vols=[64] * 64,
    )
    
    inst_ptr_off, smp_ptr_off, pat_ptr_off = writer.write_orders_and_pointers(
        orders, num_instruments, num_samples, num_patterns
    )
    
    # Write Edit History (0 entries)
    writer.buffer.write(struct.pack('<H', 0))
    
    # Write Instruments
    inst_offsets = []
    for i, sample in enumerate(rendered_samples):
        # Find track for this sample
        track_idx = None
        for ti, si in track_to_sample.items():
            if si == i + 1:
                track_idx = ti
                break
        
        track = tracks[track_idx] if track_idx is not None else tracks[0]
        
        gain_map, _ = distribute_gain(
            100, track.vol,
            mixer_channels.get(track.mixch, MixerChannel(0, '', 1.0, False, {})).volume,
            mixer_channels.get(track.mixch, MixerChannel(0, '', 1.0, False, {0: 1.0})).sends.get(0, 1.0),
            project_globals['master_vol'],
        )
        
        offset = writer.write_instrument(
            name=sample.name,
            global_volume=gain_map.inst_global_vol,
            default_pan=32 | 128,
            sample_index=i + 1,
        )
        inst_offsets.append(offset)
    
    # Write Sample Headers
    smp_header_offsets = []
    smp_ptr_positions = []
    
    for sample in rendered_samples:
        offset, ptr_pos = writer.write_sample_header(sample)
        smp_header_offsets.append(offset)
        smp_ptr_positions.append(ptr_pos)
    
    # Write Patterns
    pat_offsets = []
    for pat_idx in range(num_patterns):
        start_row = pat_idx * rows_per_pattern
        end_row = min(start_row + rows_per_pattern, total_rows)
        rows_in_pattern = end_row - start_row
        
        # Create sub-channels with only events in this pattern
        pattern_channels = []
        for ch in it_channels[:num_channels]:
            sub_ch = ITChannel(
                instrument_index=ch.instrument_index,
                events={},
                default_pan=ch.default_pan,
            )
            for row, event in ch.events.items():
                if start_row <= row < end_row:
                    local_row = row - start_row
                    sub_ch.events[local_row] = ITEvent(
                        row=local_row,
                        note=event.note,
                        instrument=event.instrument,
                        volume=event.volume,
                        effect=event.effect,
                        effect_param=event.effect_param,
                        panning=event.panning,
                    )
            pattern_channels.append(sub_ch)
        
        offset = writer.write_pattern(rows_in_pattern, pattern_channels, num_channels)
        pat_offsets.append(offset)
    
    # Write Sample Data
    smp_data_offsets = []
    for sample in rendered_samples:
        offset = writer.write_sample_data(sample)
        smp_data_offsets.append(offset)
    
    # Patch parapointers
    buf = writer.buffer
    
    for i, offset in enumerate(inst_offsets):
        buf.seek(inst_ptr_off + i * 4)
        buf.write(struct.pack('<I', offset))
    
    for i, offset in enumerate(smp_header_offsets):
        buf.seek(smp_ptr_off + i * 4)
        buf.write(struct.pack('<I', offset))
    
    for i, offset in enumerate(pat_offsets):
        buf.seek(pat_ptr_off + i * 4)
        buf.write(struct.pack('<I', offset))
    
    # Patch sample data offsets in sample headers
    for i, data_offset in enumerate(smp_data_offsets):
        buf.seek(smp_ptr_positions[i])
        buf.write(struct.pack('<I', data_offset))
    
    # Write to disk
    buf.seek(0)
    with open(it_path, 'wb') as f:
        f.write(buf.read())
    
    if progress_callback:
        progress_callback(f"Conversion complete: {num_instruments} instruments, {num_channels} channels")
    
    return True


# =============================================================================
# Tkinter GUI
# =============================================================================

class LMMSConverterGUI:
    """Tkinter GUI for the LMMS to IT converter."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LMMS to IT Converter")
        self.root.geometry("600x400")
        self.root.minsize(500, 300)
        
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        
        self._create_widgets()
        self._check_dependencies()
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Input file section
        input_frame = ttk.LabelFrame(main_frame, text="Input File", padding="5")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(input_frame, text="LMMS Project (.mmp/.mmpz):").pack(anchor=tk.W)
        
        input_entry_frame = ttk.Frame(input_frame)
        input_entry_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Entry(input_entry_frame, textvariable=self.input_path, 
                  width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(input_entry_frame, text="Browse...", 
                   command=self._browse_input).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Output file section
        output_frame = ttk.LabelFrame(main_frame, text="Output File", padding="5")
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(output_frame, text="Impulse Tracker (.it):").pack(anchor=tk.W)
        
        output_entry_frame = ttk.Frame(output_frame)
        output_entry_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Entry(output_entry_frame, textvariable=self.output_path,
                  width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_entry_frame, text="Browse...",
                   command=self._browse_output).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Options section
        options_frame = ttk.LabelFrame(main_frame, text="Requirements", padding="5")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # LMMS status label (required)
        self.lmms_status = tk.StringVar(value="Checking for LMMS...")
        lmms_status_label = ttk.Label(options_frame, textvariable=self.lmms_status, 
                                       foreground="gray")
        lmms_status_label.pack(anchor=tk.W, pady=(2, 5))
        
        # Check LMMS availability
        self._check_lmms_available()
        
        # Status/Info section
        self.info_text = tk.Text(options_frame, height=5, wrap=tk.WORD)
        self.info_text.pack(fill=tk.X)
        self.info_text.insert(tk.END, "This converter requires LMMS to be installed.\n\n"
                                       "Each instrument is rendered as a single note (C4) sample using LMMS CLI.\n"
                                       "The samples are then used as instruments in the IT file.\n\n"
                                       "Supported:\n"
                                       "• Built-in synthesizers (TripleOscillator, Monstro, Nescaline, etc.)\n"
                                       "• Sample-based instruments (AudioFileProcessor, SF2Player)\n"
                                       "• VST instruments (if the VST plugins are installed)")
        self.info_text.config(state=tk.DISABLED)
        
        # Progress section
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_var = tk.StringVar(value="")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.convert_button = ttk.Button(button_frame, text="Convert", 
                                         command=self._convert)
        self.convert_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(button_frame, text="Exit", 
                   command=self.root.quit).pack(side=tk.RIGHT)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, 
                               relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _check_dependencies(self):
        """Check for required dependencies and update status."""
        missing = []
        if not HAS_NUMPY:
            missing.append("numpy")
        if not HAS_SOUNDFILE:
            missing.append("soundfile (optional, for external samples)")
        
        if missing:
            msg = f"Missing dependencies: {', '.join(missing)}"
            self.status_var.set(msg)
            if "numpy" in missing:
                self.convert_button.config(state=tk.DISABLED)
    
    def _check_lmms_available(self):
        """Check if LMMS is available on the system."""
        lmms_path = find_lmms_executable()
        if lmms_path:
            self.lmms_status.set(f"✓ LMMS found: {lmms_path}")
        else:
            self.lmms_status.set("✗ LMMS not found - conversion will fail")
            self.convert_button.config(state=tk.DISABLED)
    
    def _browse_input(self):
        """Browse for input file."""
        filename = filedialog.askopenfilename(
            title="Select LMMS Project",
            filetypes=[
                ("LMMS Project Files", "*.mmp *.mmpz"),
                ("Uncompressed LMMS Project", "*.mmp"),
                ("Compressed LMMS Project", "*.mmpz"),
                ("All Files", "*.*"),
            ]
        )
        if filename:
            self.input_path.set(filename)
            # Auto-set output path
            output = os.path.splitext(filename)[0] + ".it"
            self.output_path.set(output)
    
    def _browse_output(self):
        """Browse for output file."""
        filename = filedialog.asksaveasfilename(
            title="Save IT File",
            defaultextension=".it",
            filetypes=[
                ("Impulse Tracker Module", "*.it"),
                ("All Files", "*.*"),
            ]
        )
        if filename:
            self.output_path.set(filename)
    
    def _update_progress(self, message: str):
        """Update progress message."""
        self.progress_var.set(message)
        self.root.update_idletasks()
    
    def _convert(self):
        """Perform the conversion."""
        input_file = self.input_path.get().strip()
        output_file = self.output_path.get().strip()
        
        if not input_file:
            messagebox.showerror("Error", "Please select an input file.")
            return
        
        if not output_file:
            messagebox.showerror("Error", "Please specify an output file.")
            return
        
        if not os.path.exists(input_file):
            messagebox.showerror("Error", f"Input file does not exist:\n{input_file}")
            return
        
        # Ensure output has .it extension
        if not output_file.lower().endswith('.it'):
            output_file += '.it'
            self.output_path.set(output_file)
        
        self.convert_button.config(state=tk.DISABLED)
        self.status_var.set("Converting...")
        
        try:
            success = convert_mmp_to_it(
                input_file, 
                output_file, 
                progress_callback=self._update_progress
            )
            
            if success:
                self.status_var.set("Conversion complete!")
                # Build summary with rendering modes
                mode_summary = "Rendering modes used:\n"
                for track_name, mode in RENDERING_MODES_USED:
                    mode_summary += f"  • {track_name}: {mode}\n"
                
                # Count CLI vs fallback
                cli_count = sum(1 for _, m in RENDERING_MODES_USED if "CLI" in m)
                total = len(RENDERING_MODES_USED)
                
                messagebox.showinfo("Success", 
                    f"Successfully converted:\n{input_file}\n\nTo:\n{output_file}\n\n"
                    f"{mode_summary}"
                    f"\nAccuracy: {cli_count}/{total} tracks rendered via LMMS CLI")
            
        except ImportError as e:
            messagebox.showerror("Error", f"Missing dependency:\n{e}\n\n"
                                           "Install required packages with:\n"
                                           "pip install numpy")
        except ValueError as e:
            messagebox.showerror("Error", f"Conversion error:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error:\n{e}")
            import traceback
            traceback.print_exc()
        finally:
            self.convert_button.config(state=tk.NORMAL)
    
    def run(self):
        """Start the GUI event loop."""
        self.root.mainloop()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) >= 3:
        # Command-line mode
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        
        def progress(msg):
            print(f"  {msg}")
        
        try:
            convert_mmp_to_it(input_file, output_file, progress)
            print(f"\nConversion complete: {output_file}")
        except Exception as e:
            print(f"\nError: {e}")
            sys.exit(1)
    else:
        # GUI mode
        app = LMMSConverterGUI()
        app.run()


if __name__ == '__main__':
    main()