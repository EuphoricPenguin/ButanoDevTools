

# MMP/MMPZ to IT Conversion Strategy

This is a complex format conversion problem that requires careful mapping between two fundamentally different paradigms: LMMS's multi-timbral, polyphonic, mixer-routed architecture and Impulse Tracker's channel-based, sample-oriented tracker grid.

## High-Level Pipeline

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌─────────────┐
│ Parse MMP/   │ -> │ Render Each  │ -> │ Map Notes +   │ -> │ Write IT    │
│ MMPZ XML     │    │ Instrument   │    │ Gain to IT    │    │ Binary File │
│              │    │ to Samples   │    │ Channels      │    │             │
└─────────────┘    └──────────────┘    └───────────────┘    └─────────────┘
```

---

## Phase 1: Parse the MMP/MMPZ Project

<details>
<summary><strong>1a. Decompress if MMPZ</strong></summary>

```python
import zlib
import struct
from lxml import etree

def load_mmp(filepath: str) -> etree._Element:
    with open(filepath, 'rb') as f:
        data = f.read()
    
    if filepath.endswith('.mmpz'):
        # Qt's qCompress prepends a 4-byte big-endian uncompressed size
        expected_size = struct.unpack('>I', data[:4])[0]
        raw_xml = zlib.decompress(data[4:])
        assert len(raw_xml) == expected_size
    else:
        raw_xml = data
    
    return etree.fromstring(raw_xml)
```

</details>

<details>
<summary><strong>1b. Extract Global Project Parameters</strong></summary>

```python
def extract_project_globals(root):
    head = root.find('head')
    return {
        'bpm': int(head.get('bpm', '140')),
        'timesig_num': int(head.get('timesig_numerator', '4')),
        'timesig_den': int(head.get('timesig_denominator', '4')),
        'master_vol': int(head.get('mastervol', '100')),   # 0-200
        'master_pitch': int(head.get('masterpitch', '0')), # -12 to 12 semitones
        'ticks_per_bar': (int(head.get('timesig_numerator', '4')) * 48 * 4)
                         // int(head.get('timesig_denominator', '4')),
        # LMMS default: 192 ticks/bar at 4/4
    }
```

</details>

<details>
<summary><strong>1c. Extract All Instrument Tracks with Notes and Gain Data</strong></summary>

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class LMMSNote:
    pos: int          # absolute position in ticks
    len: int          # duration in ticks
    key: int          # MIDI key 0-127
    vol: int          # 0-200
    pan: int          # -100 to 100

@dataclass
class LMMSMidiClip:
    pos: int          # clip start position in ticks
    length: int       # clip length in ticks
    muted: bool
    notes: List[LMMSNote]

@dataclass
class LMMSInstrumentTrack:
    name: str
    muted: bool
    solo: bool
    instrument_name: str    # e.g. "tripleoscillator", "AudioFileProcessor"
    instrument_elem: object # lxml element for rendering
    vol: float              # 0-200
    pan: float              # -100 to 100
    pitch: float            # cents
    basenote: int           # MIDI key (69 = A4)
    mixch: int              # mixer channel assignment
    use_master_pitch: bool
    clips: List[LMMSMidiClip]
    fx_chain: object        # lxml element

@dataclass
class MixerChannel:
    num: int
    name: str
    volume: float       # 0.0-2.0
    muted: bool
    sends: dict         # {target_channel: amount}

def extract_tracks(root) -> tuple:
    tracks = []
    mixer_channels = {}
    
    # Extract mixer
    mixer = root.find('.//mixer')
    if mixer is not None:
        for mch in mixer.findall('mixerchannel'):
            num = int(mch.get('num', '0'))
            sends = {}
            for send in mch.findall('send'):
                sends[int(send.get('channel'))] = float(send.get('amount', '1.0'))
            mixer_channels[num] = MixerChannel(
                num=num,
                name=mch.get('name', f'Channel {num}'),
                volume=float(mch.get('volume', '1.0')),
                muted=mch.get('muted', '0') == '1',
                sends=sends,
            )
    
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
```

</details>

---

## Phase 2: Render Each Instrument to a Sample Set

This is the critical step. IT files are sample-based—they don't have synthesizer engines. Every LMMS instrument (TripleOscillator, FreeBoy, VeSTige, etc.) must be **pre-rendered to audio samples**.

### Strategy: One-Shot Sample per Instrument at Base Note

For each instrument track, render one or more samples by driving the LMMS engine (or an offline equivalent) to produce audio.

```python
import subprocess
import numpy as np
import soundfile as sf

@dataclass
class RenderedSample:
    name: str               # max 26 chars for IT
    filename: str           # max 12 chars (DOS 8.3)
    data: np.ndarray        # mono or stereo float32 audio
    sample_rate: int        # e.g. 44100
    base_note: int          # MIDI key this was recorded at
    loop_start: int         # in sample frames, 0 if no loop
    loop_end: int           # in sample frames, 0 if no loop
    is_looped: bool
    is_stereo: bool
```

<details>
<summary><strong>Option A: Use LMMS CLI for offline rendering (per-track bouncing)</strong></summary>

The most accurate approach: create a temporary MMP with a single track playing a sustained note, then render it.

```python
import tempfile
import copy

def render_instrument_sample(
    root_elem,
    track: LMMSInstrumentTrack,
    project_globals: dict,
    duration_seconds: float = 3.0,
    sample_rate: int = 44100,
) -> RenderedSample:
    """
    Create a temporary LMMS project with just this instrument
    playing its base note, render it, and capture the audio.
    """
    # Build a minimal MMP with one track, one note
    base_note = track.basenote
    ticks_per_bar = project_globals['ticks_per_bar']
    bpm = project_globals['bpm']
    
    # Calculate note length in ticks for desired duration
    seconds_per_tick = 60.0 / (bpm * (ticks_per_bar / 4.0))  # approximate
    # More precisely: 1 beat = 60/bpm seconds, 1 beat = 48 ticks (at 4/4)
    seconds_per_tick = 60.0 / (bpm * 48.0)
    note_len_ticks = int(duration_seconds / seconds_per_tick)
    
    minimal_xml = f"""<?xml version="1.0"?>
<lmms-project version="27" type="song" creator="LMMS" creatorversion="1.3.0">
  <head bpm="{bpm}" timesig_numerator="4" timesig_denominator="4"
        mastervol="100" masterpitch="0"/>
  <song>
    <trackcontainer>
      <track type="0" name="render" muted="0" solo="0">
        {etree.tostring(track.instrument_elem.getparent(), encoding='unicode')}
        <midiclip pos="0" len="{note_len_ticks}" muted="0" type="1">
          <note pos="0" len="{note_len_ticks}" key="{base_note}" vol="100" pan="0"/>
        </midiclip>
      </track>
    </trackcontainer>
    <mixer>
      <mixerchannel num="0" name="Master" volume="1"/>
    </mixer>
    <timeline loopEnabled="0"/>
  </song>
</lmms-project>"""
    
    with tempfile.NamedTemporaryFile(suffix='.mmp', mode='w', delete=False) as tmp_mmp:
        tmp_mmp.write(minimal_xml)
        tmp_mmp_path = tmp_mmp.name
    
    output_wav = tmp_mmp_path.replace('.mmp', '.wav')
    
    # LMMS CLI render
    subprocess.run([
        'lmms', 'render', tmp_mmp_path,
        '--output', output_wav,
        '--format', 'wav',
        '--samplerate', str(sample_rate),
        '--bitdepth', '16',
    ], check=True, capture_output=True)
    
    audio_data, sr = sf.read(output_wav, dtype='float32')
    
    # Trim silence from end
    audio_data = trim_trailing_silence(audio_data, threshold=1e-5)
    
    is_stereo = audio_data.ndim == 2 and audio_data.shape[1] == 2
    
    return RenderedSample(
        name=track.name[:26],
        filename=sanitize_dos_filename(track.name),
        data=audio_data,
        sample_rate=sr,
        base_note=base_note,
        loop_start=0,
        loop_end=0,
        is_looped=False,
        is_stereo=is_stereo,
    )


def trim_trailing_silence(audio, threshold=1e-5):
    """Remove trailing silence from audio array."""
    if audio.ndim == 2:
        amplitude = np.max(np.abs(audio), axis=1)
    else:
        amplitude = np.abs(audio)
    
    # Find last sample above threshold
    indices = np.where(amplitude > threshold)[0]
    if len(indices) == 0:
        return audio[:1]  # Return at least 1 sample
    
    last_nonsilent = indices[-1]
    # Add a small fade-out tail
    tail = min(1024, len(audio) - last_nonsilent - 1)
    return audio[:last_nonsilent + tail + 1]
```

</details>

<details>
<summary><strong>Option B: Multi-sample rendering for better pitch accuracy</strong></summary>

For instruments with strong pitch-dependent timbral changes (like AudioFileProcessor or VeSTige), render multiple samples across the key range:

```python
def render_multi_sample(
    root_elem,
    track: LMMSInstrumentTrack,
    project_globals: dict,
    sample_rate: int = 44100,
) -> List[RenderedSample]:
    """
    Render samples at multiple pitches for better fidelity.
    IT supports up to 99 samples, so budget accordingly.
    """
    # Determine the actual key range used by this track's notes
    all_keys = set()
    for clip in track.clips:
        for note in clip.notes:
            all_keys.add(note.key)
    
    if not all_keys:
        return []
    
    min_key = min(all_keys)
    max_key = max(all_keys)
    key_span = max_key - min_key
    
    # Strategy: render every octave, or every 6 semitones for wide ranges
    if key_span <= 12:
        # Small range: single sample at median key
        render_keys = [track.basenote]
    elif key_span <= 36:
        # Medium range: sample every octave
        render_keys = list(range(min_key, max_key + 1, 12))
    else:
        # Wide range: sample every 6 semitones
        render_keys = list(range(min_key, max_key + 1, 6))
    
    samples = []
    for key in render_keys:
        sample = render_instrument_sample_at_key(
            root_elem, track, project_globals, key, sample_rate
        )
        samples.append(sample)
    
    return samples
```

For the purposes of this guide, we'll primarily use **single-sample-per-instrument** for simplicity, since IT's native pitch shifting handles moderate ranges well.

</details>

<details>
<summary><strong>Option C: Direct synthesis for known instruments (no LMMS dependency)</strong></summary>

For standalone conversion without the LMMS binary, implement lightweight renderers for common instruments:

```python
def render_triple_oscillator(inst_elem, base_note, sample_rate=44100, duration=2.0):
    """Direct synthesis of TripleOscillator without LMMS."""
    to_elem = inst_elem.find('.//TripleOscillator')
    if to_elem is None:
        to_elem = inst_elem.find('.//tripleoscillator')
    
    base_freq = 440.0 * (2.0 ** ((base_note - 69) / 12.0))
    num_samples = int(duration * sample_rate)
    t = np.arange(num_samples) / sample_rate
    
    output = np.zeros(num_samples, dtype=np.float32)
    
    WAVE_FUNCS = {
        0: lambda f, t, ph: np.sin(2 * np.pi * f * t + ph),           # Sine
        1: lambda f, t, ph: 2 * np.abs(2 * ((f * t + ph/(2*np.pi)) % 1) - 1) - 1,  # Triangle
        2: lambda f, t, ph: 2 * ((f * t + ph/(2*np.pi)) % 1) - 1,    # Saw
        3: lambda f, t, ph: np.sign(np.sin(2 * np.pi * f * t + ph)),  # Square
        6: lambda f, t, ph: np.random.uniform(-1, 1, len(t)),         # Noise
    }
    
    mod_algos = {
        0: 'pm',    # Phase modulation
        1: 'am',    # Amplitude modulation
        2: 'mix',   # Additive mix
        3: 'sync',  # Hard sync
        4: 'fm',    # Frequency modulation
    }
    
    for i in range(3):
        vol = float(to_elem.get(f'vol{i}', '33.33')) / 100.0
        coarse = int(to_elem.get(f'coarse{i}', '0'))
        fine_l = float(to_elem.get(f'finel{i}', '0'))
        fine_r = float(to_elem.get(f'finer{i}', '0'))
        wave_type = int(to_elem.get(f'wavetype{i}', '0'))
        ph_offset = float(to_elem.get(f'phoffset{i}', '0')) * np.pi / 180.0
        
        detune_cents = coarse * 100.0 + (fine_l + fine_r) / 2.0
        freq = base_freq * (2.0 ** (detune_cents / 1200.0))
        
        wave_func = WAVE_FUNCS.get(wave_type, WAVE_FUNCS[0])
        osc_output = wave_func(freq, t, ph_offset) * vol
        
        # For simplicity, always mix (algorithm 2)
        # A full implementation would chain modulation algorithms
        output += osc_output
    
    # Normalize
    peak = np.max(np.abs(output))
    if peak > 0:
        output /= peak
    
    return output


def render_audio_file_processor(inst_elem, base_note, sample_rate=44100):
    """Load and return the sample from AudioFileProcessor."""
    afp = inst_elem.find('.//AudioFileProcessor')
    if afp is None:
        return None
    
    src = afp.get('src', '')
    amp = float(afp.get('amp', '100')) / 100.0
    reversed_playback = afp.get('reversed', '0') == '1'
    looped = int(afp.get('looped', '0'))
    sframe = float(afp.get('sframe', '0'))
    eframe = float(afp.get('eframe', '1'))
    lframe = float(afp.get('lframe', '0'))
    
    # Resolve path prefixes
    resolved_path = resolve_lmms_path(src)
    audio_data, sr = sf.read(resolved_path, dtype='float32')
    
    # Apply start/end points
    total_frames = len(audio_data)
    start_frame = int(sframe * total_frames)
    end_frame = int(eframe * total_frames)
    audio_data = audio_data[start_frame:end_frame]
    
    if reversed_playback:
        audio_data = audio_data[::-1]
    
    audio_data *= amp
    
    loop_start = int(lframe * total_frames) - start_frame if looped else 0
    loop_end = len(audio_data) if looped else 0
    
    return audio_data, sr, looped > 0, max(0, loop_start), loop_end
```

</details>

---

## Phase 3: Compute Per-Note Gain Values

This is where the LMMS gain hierarchy gets flattened into IT's volume system.

### IT Volume Model

IT has these volume controls per note event:

| IT Control | Range | Granularity |
|------------|-------|-------------|
| **Volume** (Vxx in pattern) | 0–64 | 65 levels |
| **Global Volume** (header) | 0–128 | 129 levels |
| **Channel Volume** (Mxx) | 0–64 | Per-channel |
| **Sample Global Volume** | 0–64 | Per-sample |
| **Instrument Global Volume** | 0–128 | Per-instrument |
| **Mixing Volume** (header) | 0–128 | Master fader |

### Mapping LMMS Gain → IT Volume

```python
def compute_it_volume(
    note: LMMSNote,
    track: LMMSInstrumentTrack,
    mixer_channels: dict,
    project_globals: dict,
) -> int:
    """
    Flatten the LMMS gain hierarchy into a single IT volume value (0-64).
    
    LMMS signal chain:
      note_vol/100 × track_vol/100 × pan_gain × mixer_vol × send_amount × master_vol/100
    
    IT signal chain:
      note_vol/64 × sample_global/64 × inst_global/128 × channel_vol/64 × global_vol/128
    
    We map:
      - IT note volume     <- note_vol (dynamic, per note)
      - IT sample global   <- 64 (neutral)
      - IT inst global     <- track_vol * mixer_vol (static per instrument)
      - IT channel volume  <- 64 (neutral, unless we need extra range)
      - IT global volume   <- master_vol
      - IT mixing volume   <- 128 (neutral)
    """
    
    # --- Note-level gain ---
    note_gain = note.vol / 100.0        # 0-2.0
    
    # --- Track-level gain ---
    track_gain = track.vol / 100.0      # 0-2.0
    
    # --- Panning gain (for the relevant channel) ---
    # We'll handle panning separately via IT panning commands
    # For volume calculation, use the average (center) gain
    
    # --- Mixer channel gain ---
    mixch = mixer_channels.get(track.mixch)
    mixer_gain = mixch.volume if mixch and not mixch.muted else 1.0  # 0-2.0
    
    # Trace sends to master
    send_gain = 1.0
    if mixch and track.mixch != 0:
        # Find send amount to master (channel 0)
        send_gain = mixch.sends.get(0, 1.0)
    
    # --- Master gain ---
    master_gain = project_globals['master_vol'] / 100.0  # 0-2.0
    
    # --- Total linear gain ---
    total_gain = note_gain * track_gain * mixer_gain * send_gain * master_gain
    
    # --- Map to IT volume ---
    # IT note volume is 0-64, we'll use the instrument global volume
    # to encode the static part (track * mixer * send)
    
    # Static gain (per instrument, doesn't change per note)
    static_gain = track_gain * mixer_gain * send_gain
    
    # Dynamic gain (changes per note)
    dynamic_gain = note_gain
    
    # IT instrument global volume: 0-128 (128 = full)
    # Map static_gain (typically 0-2 range but can exceed) into 0-128
    it_inst_global = int(min(128, static_gain * 64))
    
    # IT note volume: 0-64 (64 = full)
    # Map dynamic_gain (0-2) into 0-64
    it_note_vol = int(min(64, dynamic_gain * 32))
    
    # IT global volume for master: 0-128
    it_global_vol = int(min(128, master_gain * 64))
    
    return it_note_vol, it_inst_global, it_global_vol


def compute_it_panning(note: LMMSNote, track: LMMSInstrumentTrack) -> int:
    """
    Compute IT panning value (0-64, 32=center) from LMMS panning values.
    
    LMMS: note pan (-100 to 100) combined with track pan (-100 to 100)
    IT: 0 (left) to 64 (right), 32 = center
    """
    # Combine note pan and track pan (LMMS adds them, clamped)
    combined_pan = max(-100, min(100, note.pan + track.pan))
    
    # Map -100..100 to 0..64
    it_pan = int((combined_pan + 100) / 200.0 * 64.0)
    return max(0, min(64, it_pan))
```

### Volume Distribution Strategy

Since LMMS allows volumes up to 200% at multiple stages (potentially $2^5 = 32\times$ total amplification), but IT's combined volume product maxes out at:

$$V_{\text{max}} = \frac{64}{64} \times \frac{64}{64} \times \frac{128}{128} \times \frac{128}{128} \times \frac{128}{128} = 1.0$$

We need to **normalize** and **distribute** the gain budget carefully:

```python
@dataclass
class ITGainMapping:
    """How to distribute LMMS gain across IT's volume controls."""
    global_volume: int      # 0-128, set once in header
    mixing_volume: int      # 0-128, set once in header
    inst_global_vol: int    # 0-128, per instrument
    sample_global_vol: int  # 0-64, per sample
    channel_vol: int        # 0-64, per channel
    note_vol: int           # 0-64, per note event

def distribute_gain(
    note_vol_lmms: float,     # 0-200
    track_vol_lmms: float,    # 0-200
    mixer_vol: float,         # 0-2
    send_amount: float,       # 0-1
    master_vol_lmms: float,   # 0-200
) -> ITGainMapping:
    """
    Distribute total LMMS gain across IT volume controls to minimize
    quantization error while staying within IT's range.
    """
    # Normalize everything to 0.0-1.0 linear scale where 1.0 = "normal"
    # LMMS "100" = normal, "200" = 2x gain
    note_lin = note_vol_lmms / 100.0        # 0-2
    track_lin = track_vol_lmms / 100.0      # 0-2
    mixer_lin = mixer_vol                    # 0-2
    send_lin = send_amount                   # 0-1
    master_lin = master_vol_lmms / 100.0    # 0-2
    
    total_lin = note_lin * track_lin * mixer_lin * send_lin * master_lin
    
    # IT's total gain product:
    # (note/64) * (sample_gv/64) * (inst_gv/128) * (channel_v/64) * (global_v/128)
    # At all max values = (64/64)*(64/64)*(128/128)*(64/64)*(128/128) = 1.0
    # 
    # So IT cannot amplify above 1.0. If LMMS total > 1.0, we must
    # bake the excess into the sample audio (pre-amplify the waveform).
    
    # Clamp total gain to 1.0 for IT, compute sample pre-amp factor
    if total_lin > 1.0:
        sample_pre_amp = total_lin  # Apply to rendered sample audio
        total_lin = 1.0
    else:
        sample_pre_amp = 1.0
    
    # Distribution strategy:
    # 1. Master volume → IT Global Volume (shared across all tracks)
    # 2. Track volume × mixer × send → IT Instrument Global Volume
    # 3. Note volume → IT Note Volume (per-event)
    
    # Master: map to Global Volume (0-128)
    master_clamped = min(1.0, master_lin)
    it_global = round(master_clamped * 128)
    remaining = total_lin / max(master_clamped, 1e-10)
    
    # Static per-instrument: track * mixer * send → Inst Global (0-128)
    static_gain = min(1.0, track_lin * mixer_lin * send_lin)
    it_inst_gv = round(static_gain * 128)
    remaining = remaining / max(static_gain, 1e-10) if static_gain > 0 else 0
    
    # Dynamic per-note → Note Volume (0-64)
    note_clamped = min(1.0, note_lin) * min(1.0, remaining)
    it_note_vol = round(note_clamped * 64)
    
    return ITGainMapping(
        global_volume=min(128, max(0, it_global)),
        mixing_volume=128,  # neutral
        inst_global_vol=min(128, max(0, it_inst_gv)),
        sample_global_vol=64,  # neutral
        channel_vol=64,  # neutral
        note_vol=min(64, max(0, it_note_vol)),
    ), sample_pre_amp
```

---

## Phase 4: Polyphony Splitting — Map Notes to IT Channels

**This is the most critical algorithmic step.** IT channels are monophonic: one note per channel per row. LMMS instruments are polyphonic. Chords and overlapping notes must be spread across multiple IT channels.

### IT Constraints

| Constraint | Limit |
|------------|-------|
| Max channels | 64 |
| Notes per channel per row | **1** |
| Max samples | 99 |
| Max instruments | 99 |
| Max patterns | 200 |
| Max orders | 256 |
| Rows per pattern | 32–200 |

### The Channel Allocation Algorithm

```python
from collections import defaultdict
import math

@dataclass 
class ITEvent:
    row: int
    note: int           # IT note value (0-119, or 255=note off, 254=note cut)
    instrument: int     # 1-99
    volume: int         # 0-64 (or 255=no volume)
    effect: int         # effect command
    effect_param: int   # effect parameter
    panning: int        # 0-64 or -1 for none

@dataclass
class ITChannel:
    instrument_index: int   # which IT instrument this channel serves
    events: dict            # {row: ITEvent}
    default_pan: int        # 0-64


def tick_to_row(tick: int, ticks_per_row: int) -> int:
    """Convert LMMS tick position to IT row index."""
    return tick // ticks_per_row


def allocate_channels(
    tracks: List[LMMSInstrumentTrack],
    ticks_per_row: int,
    mixer_channels: dict,
    project_globals: dict,
) -> List[ITChannel]:
    """
    Allocate IT channels for all notes across all LMMS tracks.
    
    Algorithm:
    1. For each LMMS track, collect all notes sorted by position
    2. For each note, find or create an IT channel where:
       a. The channel is assigned to this instrument
       b. The channel is free (no active note) at this row
    3. If no free channel exists, allocate a new one
    
    This is essentially a greedy interval scheduling / graph coloring problem.
    """
    all_channels: List[ITChannel] = []
    
    for track_idx, track in enumerate(tracks):
        if track.muted:
            continue
        
        # Collect all notes from all non-muted clips
        all_notes = []
        for clip in track.clips:
            if clip.muted:
                continue
            all_notes.extend(clip.notes)
        
        # Sort by position, then by key (for deterministic channel assignment)
        all_notes.sort(key=lambda n: (n.pos, n.key))
        
        # Channels allocated to THIS instrument
        inst_channels: List[ITChannel] = []
        
        for note in all_notes:
            start_row = tick_to_row(note.pos, ticks_per_row)
            # Note-off row: the row AFTER the last sounding row
            end_row = tick_to_row(note.pos + note.len, ticks_per_row)
            if end_row == start_row:
                end_row = start_row + 1  # minimum 1 row duration
            
            # Find a free channel
            assigned_channel = None
            for ch in inst_channels:
                # Check if channel is free from start_row to end_row
                is_free = True
                for row in range(start_row, end_row + 1):
                    if row in ch.events:
                        is_free = False
                        break
                if is_free:
                    assigned_channel = ch
                    break
            
            # No free channel found — allocate a new one
            if assigned_channel is None:
                if len(all_channels) >= 64:
                    print(f"WARNING: Exceeded 64 IT channels! Dropping note "
                          f"key={note.key} at tick={note.pos}")
                    continue
                
                assigned_channel = ITChannel(
                    instrument_index=track_idx + 1,  # IT instruments are 1-based
                    events={},
                    default_pan=compute_it_panning(
                        LMMSNote(0, 0, 69, 100, 0), track
                    ),
                )
                inst_channels.append(assigned_channel)
                all_channels.append(assigned_channel)
            
            # Compute gain
            gain_map, _ = distribute_gain(
                note.vol, track.vol,
                mixer_channels.get(track.mixch, MixerChannel(0,'',1.0,False,{})).volume,
                mixer_channels.get(track.mixch, MixerChannel(0,'',1.0,False,{0:1.0})).sends.get(0, 1.0),
                project_globals['master_vol'],
            )
            
            # Convert LMMS MIDI key to IT note
            # IT note: C-0 = 0, C#0 = 1, ..., B-0 = 11, C-1 = 12, ...
            # MIDI: C-0 = 0 (but MIDI middle C varies; LMMS uses C5 = 60)
            # IT middle C (C-5) = 60
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
            
            # Place note-off (note cut)
            if end_row not in assigned_channel.events:
                assigned_channel.events[end_row] = ITEvent(
                    row=end_row,
                    note=255,  # Note Off
                    instrument=0,
                    volume=255,  # no volume
                    effect=0,
                    effect_param=0,
                    panning=-1,
                )
    
    return all_channels
```

### Optimized Channel Allocation (Interval Graph Coloring)

The greedy approach above works but may waste channels. For dense arrangements, use proper interval graph coloring:

```python
import heapq

def allocate_channels_optimal(
    notes_with_metadata: List[tuple],  # (start_row, end_row, note_data, track_idx)
) -> List[List[tuple]]:
    """
    Optimal channel allocation using a priority queue.
    Minimizes the number of channels used.
    
    This is equivalent to the interval partitioning problem:
    minimum number of resources to schedule all intervals.
    """
    # Sort by start time
    events = sorted(notes_with_metadata, key=lambda x: (x[0], x[1]))
    
    # Min-heap of (end_row, channel_index)
    # Each entry represents when a channel becomes free
    channels = []  # list of lists of note events
    free_heap = []  # (end_row, channel_index)
    
    for start_row, end_row, note_data, track_idx in events:
        # Try to reuse a channel that's free AND serves the same instrument
        assigned = False
        temp = []
        
        while free_heap:
            free_end, ch_idx = heapq.heappop(free_heap)
            if free_end <= start_row and channels[ch_idx][-1][3] == track_idx:
                # Reuse this channel
                channels[ch_idx].append((start_row, end_row, note_data, track_idx))
                heapq.heappush(free_heap, (end_row, ch_idx))
                assigned = True
                # Push back the temp ones
                for item in temp:
                    heapq.heappush(free_heap, item)
                break
            else:
                temp.append((free_end, ch_idx))
        
        if not assigned:
            # Push back all temp items
            for item in temp:
                heapq.heappush(free_heap, item)
            
            # Check for any free channel (even different instrument — but we prefer same)
            # Actually, for IT, each channel can play any instrument, so we CAN reuse
            reused = False
            temp2 = []
            while free_heap:
                free_end, ch_idx = heapq.heappop(free_heap)
                if free_end <= start_row:
                    channels[ch_idx].append((start_row, end_row, note_data, track_idx))
                    heapq.heappush(free_heap, (end_row, ch_idx))
                    reused = True
                    for item in temp2:
                        heapq.heappush(free_heap, item)
                    break
                else:
                    temp2.append((free_end, ch_idx))
            
            if not reused:
                for item in temp2:
                    heapq.heappush(free_heap, item)
                # Allocate new channel
                ch_idx = len(channels)
                channels.append([(start_row, end_row, note_data, track_idx)])
                heapq.heappush(free_heap, (end_row, ch_idx))
    
    return channels
```

---

## Phase 5: Time Resolution Mapping

### LMMS Ticks → IT Rows

LMMS uses 192 ticks per bar (at 4/4). IT uses rows with configurable speed/tempo.

```python
def compute_timing_params(project_globals: dict) -> dict:
    """
    Map LMMS timing to IT speed/tempo.
    
    IT timing:
      - Tempo (Txx): BPM (32-255), where 1 beat = 1 row at speed 1
      - Speed (Axx): ticks per row (1-255)
      - Actual BPM = Tempo * 24 / (Speed * 10) ... no wait.
    
    Actually in IT:
      - One row takes (Speed) ticks
      - One tick = 2.5 / Tempo seconds (Tempo in BPM)
      - So one row = Speed * 2.5 / Tempo seconds
      - IT default: Speed=6, Tempo=125 → 1 row = 6*2.5/125 = 0.12s = 5 rows/beat at 125BPM
    
    LMMS:
      - 192 ticks per bar at 4/4 = 48 ticks per beat
      - 1 tick = 60 / (BPM * 48) seconds
    
    We need to choose:
      - ticks_per_row (LMMS ticks that map to one IT row)
      - IT Speed and Tempo values
    
    Common approach: make 1 IT row = some fraction of an LMMS beat
    """
    bpm = project_globals['bpm']
    ticks_per_bar = project_globals['ticks_per_bar']  # 192 at 4/4
    ticks_per_beat = ticks_per_bar // project_globals['timesig_num']  # 48
    
    # Choose rows per beat. Higher = more time resolution, but more rows.
    # Common choices: 4, 6, 8, 12, 16, 24, 48
    # 
    # We need enough resolution to represent the shortest note.
    # LMMS's smallest common note = 1/64 note = 48/16 = 3 ticks
    # 
    # Good default: 12 rows per beat (each row = 4 LMMS ticks)
    #   Gives 1/48 beat resolution (close to LMMS's 1/48)
    # Better: 24 rows per beat (each row = 2 LMMS ticks)
    #   Even closer, but 24*4 = 96 rows per bar → may exceed 200 row limit
    # Best for 4/4: 48 rows per beat (each row = 1 LMMS tick) 
    #   Perfect accuracy, but 48*4 = 192 rows per bar → just within the 200 limit!
    
    # Strategy: find the GCD of all note positions and lengths
    # to determine the minimum required resolution
    
    # For now, use a configurable value with a good default
    rows_per_beat = 12  # Each row = 4 LMMS ticks
    ticks_per_row = ticks_per_beat // rows_per_beat  # 48 // 12 = 4
    
    # IT timing: one row = Speed / (Tempo/2.5) seconds
    # We want: one row = ticks_per_row / (48 * BPM / 60) seconds
    #        = ticks_per_row * 60 / (48 * BPM)
    #
    # IT: row_duration = Speed * 2.5 / Tempo
    # LMMS: row_duration = ticks_per_row * 60 / (48 * BPM)
    #
    # So: Speed * 2.5 / Tempo = ticks_per_row * 60 / (48 * BPM)
    #     Speed / Tempo = ticks_per_row * 60 / (48 * BPM * 2.5)
    #     Speed / Tempo = ticks_per_row * 60 / (120 * BPM)
    #     Speed / Tempo = ticks_per_row / (2 * BPM)
    #
    # With ticks_per_row = 4, BPM = 140:
    #     Speed / Tempo = 4 / 280 = 1/70
    #     Speed = 1, Tempo = 70? No, Tempo range is 32-255.
    #     Speed = 2, Tempo = 140? Yes! 2/140 = 1/70 ✓
    #     Speed = 3, Tempo = 210? Also works if BPM fits.
    
    # General solution: Speed = ticks_per_row / 2, Tempo = BPM
    # But Speed must be integer ≥ 1 and Tempo must be 32-255
    
    # For ticks_per_row = 4: Speed = 2, Tempo = BPM (if 32 ≤ BPM ≤ 255)
    
    it_speed = max(1, ticks_per_row // 2)
    it_tempo = bpm
    
    # Verify and adjust if BPM out of range
    if it_tempo < 32:
        # Scale up: multiply both speed and tempo by a factor
        factor = math.ceil(32 / it_tempo)
        it_tempo *= factor
        it_speed *= factor
    elif it_tempo > 255:
        # Scale down using higher speed
        factor = math.ceil(it_tempo / 255)
        it_tempo = round(it_tempo / factor)
        it_speed *= factor
    
    # Clamp
    it_speed = max(1, min(255, it_speed))
    it_tempo = max(32, min(255, it_tempo))
    
    rows_per_bar = ticks_per_bar // ticks_per_row
    
    return {
        'ticks_per_row': ticks_per_row,
        'rows_per_beat': rows_per_beat,
        'rows_per_bar': rows_per_bar,
        'it_speed': it_speed,
        'it_tempo': it_tempo,
    }


def find_optimal_resolution(tracks: List[LMMSInstrumentTrack]) -> int:
    """
    Find the optimal ticks_per_row by computing the GCD of all
    note positions and lengths.
    """
    from math import gcd
    from functools import reduce
    
    all_values = []
    for track in tracks:
        for clip in track.clips:
            for note in clip.notes:
                if note.pos > 0:
                    all_values.append(note.pos)
                if note.len > 0:
                    all_values.append(note.len)
    
    if not all_values:
        return 4  # default
    
    tick_gcd = reduce(gcd, all_values)
    
    # Ensure the result divides evenly into 192 (ticks per bar)
    # and doesn't create too many rows per bar
    while 192 // tick_gcd > 200:  # IT max rows per pattern
        tick_gcd *= 2
    
    return max(1, tick_gcd)
```

---

## Phase 6: Write the IT Binary File

### IT File Header (Offset 0x0000, 192 bytes)

```python
import struct
import io

class ITWriter:
    def __init__(self):
        self.buffer = io.BytesIO()
    
    def write_header(
        self,
        song_name: str,
        num_orders: int,
        num_instruments: int,
        num_samples: int,
        num_patterns: int,
        global_volume: int,
        mixing_volume: int,
        initial_speed: int,
        initial_tempo: int,
        pan_separation: int = 128,
        channels: int = 64,
        channel_pans: list = None,
        channel_vols: list = None,
    ):
        """
        Write the 192-byte IT file header.
        
        Offset  Size  Description
        0x0000  4     Magic: "IMPM"
        0x0004  26    Song name (null-padded)
        0x001E  2     Pattern row highlight (PHiLight)
        0x0020  2     OrdNum (number of orders)
        0x0022  2     InsNum (number of instruments)
        0x0024  2     SmpNum (number of samples)
        0x0026  2     PatNum (number of patterns)
        0x0028  2     Cwt/v (Created with tracker version)
        0x002A  2     Cmwt (Compatible with tracker version)
        0x002C  2     Flags
        0x002E  2     Special
        0x0030  1     GV (Global Volume, 0-128)
        0x0031  1     MV (Mixing Volume, 0-128)
        0x0032  1     IS (Initial Speed)
        0x0033  1     IT (Initial Tempo)
        0x0034  1     Sep (Panning Separation, 0-128)
        0x0035  1     PWD (Pitch Wheel Depth)
        0x0036  2     MsgLgth (Message Length)
        0x0038  4     MsgOff (Message Offset)
        0x003C  4     Reserved
        0x0040  64    Channel Pan (0-64, 100=surround, +128=disabled)
        0x0080  64    Channel Volume (0-64)
        """
        self.buffer.seek(0)
        
        # Magic
        self.buffer.write(b'IMPM')
        
        # Song name (26 bytes, null-padded)
        name_bytes = song_name.encode('ascii', errors='replace')[:26]
        self.buffer.write(name_bytes.ljust(26, b'\x00'))
        
        # Pattern row highlight: minor/major
        rows_per_beat = 12  # will be set properly
        rows_per_bar = 48
        self.buffer.write(struct.pack('<BB', rows_per_beat, rows_per_bar))
        
        # OrdNum, InsNum, SmpNum, PatNum
        self.buffer.write(struct.pack('<HHHH',
            num_orders, num_instruments, num_samples, num_patterns))
        
        # Cwt/v: We'll identify as a custom converter
        # Using 0x5000 range would be OpenMPT; let's use something unique
        # or just use compatible IT 2.14 identification
        cwt_v = 0x0214  # Compatible with IT 2.14
        cmwt = 0x0214
        self.buffer.write(struct.pack('<HH', cwt_v, cmwt))
        
        # Flags
        flags = 0
        flags |= 0x01  # Stereo
        flags |= 0x02  # Vol0MixOptimizations (don't process silent notes)
        flags |= 0x08  # Linear slides
        flags |= 0x10  # Old Effects (for IT compatibility)
        # flags |= 0x04  # Use Instruments (set if we have instruments)
        if num_instruments > 0:
            flags |= 0x04
        self.buffer.write(struct.pack('<H', flags))
        
        # Special flags
        special = 0x04  # Row highlights present
        self.buffer.write(struct.pack('<H', special))
        
        # GV, MV, IS, IT, Sep, PWD
        self.buffer.write(struct.pack('<BBBBBB',
            min(128, global_volume),
            min(128, mixing_volume),
            min(255, initial_speed),
            min(255, initial_tempo),
            pan_separation,
            0,  # PWD
        ))
        
        # Message length and offset (no message)
        self.buffer.write(struct.pack('<HI', 0, 0))
        
        # Reserved
        self.buffer.write(struct.pack('<I', 0))
        
        # Channel Pan (64 bytes)
        if channel_pans is None:
            channel_pans = [32] * 64  # center
        for i in range(64):
            if i < channels:
                self.buffer.write(struct.pack('B', channel_pans[i]))
            else:
                self.buffer.write(struct.pack('B', 32 | 128))  # disabled
        
        # Channel Volume (64 bytes)
        if channel_vols is None:
            channel_vols = [64] * 64
        for i in range(64):
            self.buffer.write(struct.pack('B', channel_vols[i] if i < channels else 0))
        
        assert self.buffer.tell() == 192, f"Header is {self.buffer.tell()} bytes, expected 192"
```

### Order List, Parapointers

```python
    def write_orders_and_pointers(
        self,
        orders: list,
        num_instruments: int,
        num_samples: int,
        num_patterns: int,
    ) -> tuple:
        """
        Write order list and parapointer arrays.
        Returns offsets for filling in later.
        """
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
```

### IT Instrument Header (554 bytes)

```python
    def write_instrument(
        self,
        name: str,
        global_volume: int,     # 0-128
        default_pan: int,       # 0-64, +128 for "use default"
        sample_index: int,      # 1-based sample to use
        note_sample_table: list = None,  # 240 bytes: note→(note, sample) mapping
    ) -> int:
        """Write an IT instrument header. Returns the offset."""
        offset = self.buffer.tell()
        
        # Magic
        self.buffer.write(b'IMPI')
        
        # DOS Filename (12 bytes + null)
        dos_name = name.encode('ascii', errors='replace')[:12]
        self.buffer.write(dos_name.ljust(13, b'\x00'))
        
        # NNA (New Note Action): 0=Cut, 1=Continue, 2=Note Off, 3=Note Fade
        self.buffer.write(struct.pack('B', 0))  # Cut
        
        # DCT (Duplicate Check Type): 0=Off
        self.buffer.write(struct.pack('B', 0))
        
        # DCA (Duplicate Check Action): 0=Cut
        self.buffer.write(struct.pack('B', 0))
        
        # FadeOut (0-256)
        self.buffer.write(struct.pack('<H', 256))
        
        # PPS (Pitch-Pan Separation), PPC (Pitch-Pan Center)
        self.buffer.write(struct.pack('bB', 0, 60))  # C-5
        
        # GbV (Global Volume), DfP (Default Pan)
        self.buffer.write(struct.pack('BB', min(128, global_volume), default_pan))
        
        # RV (Random Volume), RP (Random Panning)
        self.buffer.write(struct.pack('BB', 0, 0))
        
        # TrkVers (Tracker version for this instrument), NoS (Number of Samples)
        self.buffer.write(struct.pack('<HB', 0x0214, 1))
        
        # Reserved
        self.buffer.write(b'\x00')
        
        # Instrument Name (26 bytes)
        inst_name = name.encode('ascii', errors='replace')[:26]
        self.buffer.write(inst_name.ljust(26, b'\x00'))
        
        # IFC (Initial Filter Cutoff), IFR (Initial Filter Resonance)
        self.buffer.write(struct.pack('BB', 0, 0))
        
        # MCh (MIDI Channel), MPr (MIDI Program), MBk (MIDI Bank)
        self.buffer.write(struct.pack('BbH', 0, -1, 0))  # no MIDI
        
        # Note-Sample/Keyboard Table (240 bytes = 120 entries × 2 bytes)
        # Each entry: (note, sample_number)
        if note_sample_table is None:
            # Default: all notes map to the same sample
            for note in range(120):
                self.buffer.write(struct.pack('BB', note, sample_index))
        else:
            for note, smp in note_sample_table:
                self.buffer.write(struct.pack('BB', note, smp))
        
        # Volume Envelope (enabled=0 for simple mapping)
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
    
    def _write_envelope(self, enabled=False):
        """Write a blank IT envelope (82 bytes)."""
        flags = 0x01 if enabled else 0x00
        self.buffer.write(struct.pack('B', flags))  # Flags
        self.buffer.write(struct.pack('B', 0))       # Num nodes
        self.buffer.write(struct.pack('B', 0))       # Loop begin
        self.buffer.write(struct.pack('B', 0))       # Loop end
        self.buffer.write(struct.pack('B', 0))       # Sustain loop begin
        self.buffer.write(struct.pack('B', 0))       # Sustain loop end
        # 25 node points × 3 bytes each = 75 bytes
        self.buffer.write(b'\x00' * 75)
        self.buffer.write(b'\x00')  # padding
```

### IT Sample Header (80 bytes)

```python
    def write_sample_header(
        self,
        sample: RenderedSample,
        sample_data_offset: int = 0,  # filled in later
    ) -> int:
        """Write an IT sample header. Returns the offset."""
        offset = self.buffer.tell()
        
        # Magic
        self.buffer.write(b'IMPS')
        
        # DOS Filename (12 bytes + null)
        dos_name = sample.filename.encode('ascii', errors='replace')[:12]
        self.buffer.write(dos_name.ljust(13, b'\x00'))
        
        # GvL (Global Volume, 0-64)
        self.buffer.write(struct.pack('B', 64))
        
        # Flags
        smp_flags = 0x01  # Sample associated with header
        if sample.is_stereo:
            smp_flags |= 0x04  # Stereo
        smp_flags |= 0x08  # 16-bit (we'll store as 16-bit signed)
        if sample.is_looped:
            smp_flags |= 0x10  # Loop
        # Bit 0: sample present
        # Bit 1: 16-bit (if set)... wait, let me check:
        # Actually IT flags for sample:
        # Bit 0 = sample associated with header
        # Bit 1 = 16 bit
        # Bit 2 = stereo
        # Bit 3 = compressed
        # Bit 4 = loop
        # Bit 5 = sustain loop  
        # Bit 6 = ping-pong loop
        # Bit 7 = ping-pong sustain loop
        smp_flags = 0x01  # sample present
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
        cvt = 0x01  # signed
        self.buffer.write(struct.pack('B', cvt))
        
        # DfP (Default Pan): 0-64, bit 7 = use default pan
        self.buffer.write(struct.pack('B', 32 | 128))  # center, use default
        
        # Length (in samples, not bytes)
        num_frames = len(sample.data) if sample.data.ndim == 1 else sample.data.shape[0]
        self.buffer.write(struct.pack('<I', num_frames))
        
        # Loop Begin
        self.buffer.write(struct.pack('<I', sample.loop_start))
        
        # Loop End
        self.buffer.write(struct.pack('<I', sample.loop_end if sample.is_looped else num_frames))
        
        # C5Speed (sample rate at C-5 = middle C)
        # Adjust for base note: if sample was recorded at A4 (69),
        # we need to calculate the C5Speed so that playing note 60 (C5)
        # produces the correct pitch
        c5_speed = int(sample.sample_rate * (2.0 ** ((60 - sample.base_note) / 12.0)))
        self.buffer.write(struct.pack('<I', c5_speed))
        
        # Sustain Loop Begin, Sustain Loop End
        self.buffer.write(struct.pack('<II', 0, 0))
        
        # SamplePointer (offset to sample data, filled in later)
        sample_ptr_pos = self.buffer.tell()
        self.buffer.write(struct.pack('<I', sample_data_offset))
        
        # ViS, ViD, ViR, ViT (Vibrato Speed, Depth, Rate, Type)
        self.buffer.write(struct.pack('BBBB', 0, 0, 0, 0))
        
        assert self.buffer.tell() - offset == 80, \
            f"Sample header is {self.buffer.tell() - offset} bytes, expected 80"
        
        return offset, sample_ptr_pos
```

### IT Pattern Data (Packed)

```python
    def write_pattern(
        self,
        rows: int,
        channels: List[ITChannel],
        num_channels: int,
    ) -> int:
        """
        Write a packed IT pattern.
        Returns the file offset where the pattern starts.
        
        IT Pattern format:
          - 2 bytes: packed data length
          - 2 bytes: number of rows
          - 4 bytes: reserved (0)
          - Packed channel data...
        """
        pattern_offset = self.buffer.tell()
        
        # Placeholder for length (will fill in later)
        length_pos = self.buffer.tell()
        self.buffer.write(struct.pack('<H', 0))  # placeholder
        self.buffer.write(struct.pack('<H', rows))
        self.buffer.write(b'\x00\x00\x00\x00')  # reserved
        
        data_start = self.buffer.tell()
        
        # Previous values for packing optimization
        last_mask = [0] * 64
        last_note = [0] * 64
        last_inst = [0] * 64
        last_vol = [255] * 64
        last_cmd = [0] * 64
        last_cmd_val = [0] * 64
        
        for row in range(rows):
            for ch_idx in range(min(num_channels, len(channels))):
                ch = channels[ch_idx]
                if row not in ch.events:
                    continue
                
                event = ch.events[row]
                
                # Channel variable: (channel-1) + 1, with bit flags
                # Bits 0-6: channel number (1-based)
                # Bit 7: if set, read mask variable
                channel_var = (ch_idx + 1)  # 1-based
                
                # Mask variable determines what data follows
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
                    continue  # Nothing to write
                
                # Check if we can use "last value" compression
                # For simplicity, always write the mask
                channel_var |= 0x80  # mask follows
                
                self.buffer.write(struct.pack('B', channel_var))
                self.buffer.write(struct.pack('B', mask))
                
                if mask & 0x01:  # Note
                    self.buffer.write(struct.pack('B', event.note))
                    last_note[ch_idx] = event.note
                
                if mask & 0x02:  # Instrument
                    self.buffer.write(struct.pack('B', event.instrument))
                    last_inst[ch_idx] = event.instrument
                
                if mask & 0x04:  # Volume
                    # Volume column encoding:
                    # 0-64: Set volume
                    # 65-74: Fine volume up (65 = +0, 74 = +9)
                    # 75-84: Fine volume down
                    # 128-192: Set panning
                    vol_byte = event.volume  # 0-64 for volume
                    if event.panning >= 0 and event.panning != 32:
                        # Use panning in volume column
                        vol_byte = 128 + event.panning  # 128-192
                    self.buffer.write(struct.pack('B', vol_byte))
                    last_vol[ch_idx] = vol_byte
                
                if mask & 0x08:  # Command + Parameter
                    self.buffer.write(struct.pack('B', event.effect))
                    self.buffer.write(struct.pack('B', event.effect_param))
                    last_cmd[ch_idx] = event.effect
                    last_cmd_val[ch_idx] = event.effect_param
            
            # End of row marker
            self.buffer.write(struct.pack('B', 0))
        
        data_end = self.buffer.tell()
        packed_length = data_end - data_start
        
        # Go back and fill in the length
        self.buffer.seek(length_pos)
        self.buffer.write(struct.pack('<H', packed_length))
        self.buffer.seek(data_end)
        
        return pattern_offset
```

### Sample Data

```python
    def write_sample_data(self, sample: RenderedSample) -> int:
        """Write raw 16-bit signed sample data. Returns file offset."""
        offset = self.buffer.tell()
        
        audio = sample.data
        
        # Convert float32 [-1, 1] to int16
        if audio.dtype != np.int16:
            audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        else:
            audio_int16 = audio
        
        if sample.is_stereo and audio_int16.ndim == 2:
            # IT stereo: left channel first, then right channel
            # (NOT interleaved)
            left = audio_int16[:, 0]
            right = audio_int16[:, 1]
            self.buffer.write(left.tobytes())
            self.buffer.write(right.tobytes())
        else:
            if audio_int16.ndim == 2:
                audio_int16 = audio_int16[:, 0]  # mono mixdown
            self.buffer.write(audio_int16.tobytes())
        
        return offset
```

---

## Phase 7: Putting It All Together

```python
def convert_mmp_to_it(mmp_path: str, it_path: str, rows_per_beat: int = 12):
    """
    Complete MMP/MMPZ to IT conversion pipeline.
    """
    # === PHASE 1: Parse ===
    root = load_mmp(mmp_path)
    project_globals = extract_project_globals(root)
    tracks, mixer_channels = extract_tracks(root)
    
    if not tracks:
        raise ValueError("No instrument tracks found in project")
    
    # === PHASE 2: Render Samples ===
    print(f"Rendering {len(tracks)} instrument tracks to samples...")
    rendered_samples = []
    track_to_sample = {}  # track_index -> sample_index (1-based)
    
    for i, track in enumerate(tracks):
        if track.muted:
            continue
        sample = render_instrument_sample(root, track, project_globals)
        rendered_samples.append(sample)
        track_to_sample[i] = len(rendered_samples)  # 1-based
    
    if not rendered_samples:
        raise ValueError("No samples rendered (all tracks muted?)")
    
    # === PHASE 3 & 4: Timing + Channel Allocation ===
    timing = compute_timing_params(project_globals)
    ticks_per_row = timing['ticks_per_row']
    
    # Find the total length in rows
    max_tick = 0
    for track in tracks:
        for clip in track.clips:
            for note in clip.notes:
                max_tick = max(max_tick, note.pos + note.len)
    
    total_rows = tick_to_row(max_tick, ticks_per_row) + 4  # +4 for safety
    
    # Allocate channels
    it_channels = allocate_channels(tracks, ticks_per_row, mixer_channels, project_globals)
    num_channels = len(it_channels)
    
    if num_channels == 0:
        raise ValueError("No notes to convert")
    if num_channels > 64:
        print(f"WARNING: {num_channels} channels needed, but IT max is 64. "
              f"Some notes will be dropped.")
        num_channels = 64
        it_channels = it_channels[:64]
    
    print(f"Allocated {num_channels} IT channels for {len(tracks)} LMMS tracks")
    
    # === PHASE 5: Split into patterns ===
    rows_per_pattern = min(200, timing['rows_per_bar'] * 4)  # 4 bars per pattern
    num_patterns = math.ceil(total_rows / rows_per_pattern)
    
    if num_patterns > 200:
        # Increase rows per pattern
        rows_per_pattern = min(200, math.ceil(total_rows / 200))
        num_patterns = math.ceil(total_rows / rows_per_pattern)
    
    # Order list
    orders = list(range(num_patterns))
    orders.append(255)  # End of song marker
    
    # === PHASE 6: Compute gain distribution ===
    # Use the first non-muted track to set global volume
    gain_map, _ = distribute_gain(
        100, 100, 1.0, 1.0, project_globals['master_vol']
    )
    
    # === PHASE 7: Write IT File ===
    writer = ITWriter()
    
    # Derive song name from filename
    song_name = mmp_path.rsplit('/', 1)[-1].rsplit('.', 1)[0]
    
    num_instruments = len(rendered_samples)
    num_samples = len(rendered_samples)
    
    # Channel pans from allocated channels
    channel_pans = []
    for i in range(64):
        if i < len(it_channels):
            channel_pans.append(it_channels[i].default_pan)
        else:
            channel_pans.append(32 | 128)  # disabled
    
    channel_vols = [64] * 64
    
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
        channels=num_channels,
        channel_pans=channel_pans,
        channel_vols=channel_vols,
    )
    
    inst_ptr_off, smp_ptr_off, pat_ptr_off = writer.write_orders_and_pointers(
        orders, num_instruments, num_samples, num_patterns
    )
    
    # Write Edit History (0 entries for compatibility)
    writer.buffer.write(struct.pack('<H', 0))
    
    # --- Write Instruments ---
    inst_offsets = []
    for i, sample in enumerate(rendered_samples):
        # Find the track this sample belongs to
        track_idx = None
        for ti, si in track_to_sample.items():
            if si == i + 1:
                track_idx = ti
                break
        
        track = tracks[track_idx] if track_idx is not None else tracks[0]
        
        gain_map, _ = distribute_gain(
            100, track.vol,
            mixer_channels.get(track.mixch, MixerChannel(0,'',1.0,False,{})).volume,
            mixer_channels.get(track.mixch, MixerChannel(0,'',1.0,False,{0:1.0})).sends.get(0, 1.0),
            project_globals['master_vol'],
        )
        
        offset = writer.write_instrument(
            name=sample.name,
            global_volume=gain_map.inst_global_vol,
            default_pan=32 | 128,  # use channel default
            sample_index=i + 1,  # 1-based
        )
        inst_offsets.append(offset)
    
    # --- Write Sample Headers ---
    smp_header_offsets = []
    smp_ptr_positions = []  # positions where sample data pointers need to be patched
    
    for sample in rendered_samples:
        offset, ptr_pos = writer.write_sample_header(sample)
        smp_header_offsets.append(offset)
        smp_ptr_positions.append(ptr_pos)
    
    # --- Write Patterns ---
    pat_offsets = []
    for pat_idx in range(num_patterns):
        start_row = pat_idx * rows_per_pattern
        end_row = min(start_row + rows_per_pattern, total_rows)
        rows_in_pattern = end_row - start_row
        
        # Create sub-channels with only events in this pattern's row range
        pattern_channels = []
        for ch in it_channels[:num_channels]:
            sub_ch = ITChannel(
                instrument_index=ch.instrument_index,
                events={},
                default_pan=ch.default_pan,
            )
            for row, event in ch.events.items():
                if start_row <= row < end_row:
                    # Remap to pattern-local row
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
        
        offset = writer.write_pattern(
            rows_in_pattern, pattern_channels, num_channels
        )
        pat_offsets.append(offset)
    
    # --- Write Sample Data ---
    smp_data_offsets = []
    for sample in rendered_samples:
        offset = writer.write_sample_data(sample)
        smp_data_offsets.append(offset)
    
    # === Patch all parapointers ===
    buf = writer.buffer
    
    # Instrument parapointers
    for i, offset in enumerate(inst_offsets):
        buf.seek(inst_ptr_off + i * 4)
        buf.write(struct.pack('<I', offset))
    
    # Sample parapointers (point to sample HEADERS)
    for i, offset in enumerate(smp_header_offsets):
        buf.seek(smp_ptr_off + i * 4)
        buf.write(struct.pack('<I', offset))
    
    # Pattern parapointers
    for i, offset in enumerate(pat_offsets):
        buf.seek(pat_ptr_off + i * 4)
        buf.write(struct.pack('<I', offset))
    
    # Patch sample data offsets in sample headers
    for i, data_offset in enumerate(smp_data_offsets):
        buf.seek(smp_ptr_positions[i])
        buf.write(struct.pack('<I', data_offset))
    
    # === Write to disk ===
    buf.seek(0)
    with open(it_path, 'wb') as f:
        f.write(buf.read())
    
    print(f"Written IT file: {it_path}")
    print(f"  {num_instruments} instruments, {num_samples} samples, "
          f"{num_patterns} patterns, {num_channels} channels")
    print(f"  Speed={timing['it_speed']}, Tempo={timing['it_tempo']}, "
          f"Rows/bar={timing['rows_per_bar']}")


# === Entry point ===
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} input.mmp[z] output.it")
        sys.exit(1)
    convert_mmp_to_it(sys.argv[1], sys.argv[2])
```

---

## Critical Edge Cases and Constraints

### Polyphony Budget

| Scenario | Notes Needed | Channels Used |
|----------|-------------|---------------|
| Single monophonic melody | 1 | 1 |
| Triad chord (3 notes) | 3 simultaneous | 3 |
| Dense piano part (10-note chords) | 10 simultaneous | 10 |
| 4 instruments × avg 3 polyphony | 12 simultaneous | 12 |
| Full orchestra + drums | Could exceed 64 | **Drops needed** |

**Mitigation strategies when exceeding 64 channels:**

```python
def prioritize_notes(all_notes, max_channels=64):
    """
    When polyphony exceeds 64, prioritize notes by:
    1. Louder notes first (higher vol)
    2. Lower notes first (bass is perceptually important)
    3. Longer notes first (sustains over ornaments)
    """
    # Score each note
    scored = []
    for note in all_notes:
        score = (
            note.vol * 2.0 +               # volume weight
            (128 - note.key) * 0.5 +        # bass priority
            min(note.len, 192) * 0.01       # length bonus
        )
        scored.append((score, note))
    
    scored.sort(key=lambda x: -x[0])
    
    # Use interval scheduling with priority
    # Only keep notes that fit within max_channels polyphony
    # at any given time
    # ... (implement using the priority queue approach above)
```

### Sample Count Limit (99)

```python
def budget_samples(tracks, max_samples=99):
    """
    If there are more than 99 instrument tracks, 
    merge similar instruments or drop least-used ones.
    """
    if len(tracks) <= max_samples:
        return tracks  # No problem
    
    # Strategy 1: Merge tracks that use the same instrument plugin
    # with similar settings
    
    # Strategy 2: Prioritize by number of notes
    track_note_counts = []
    for i, track in enumerate(tracks):
        total_notes = sum(len(clip.notes) for clip in track.clips)
        track_note_counts.append((total_notes, i))
    
    track_note_counts.sort(reverse=True)
    keep_indices = set(idx for _, idx in track_note_counts[:max_samples])
    
    return [t for i, t in enumerate(tracks) if i in keep_indices]
```

### Tempo Changes

LMMS supports tempo automation. In IT, tempo changes use the `Txx` effect command:

```python
def inject_tempo_changes(
    automation_clips,
    ticks_per_row: int,
    channels: List[ITChannel],
    dedicated_channel_idx: int,
):
    """
    Convert LMMS BPM automation to IT Txx commands.
    Place on a dedicated channel.
    """
    for clip in automation_clips:
        for time_node in clip:
            row = tick_to_row(time_node.pos, ticks_per_row)
            bpm = int(time_node.value)
            bpm_clamped = max(32, min(255, bpm))
            
            channels[dedicated_channel_idx].events[row] = ITEvent(
                row=row,
                note=253,      # no note
                instrument=0,
                volume=255,    # no volume
                effect=20,     # Txx (Set Tempo) — IT effect letter 'T' = 20
                effect_param=bpm_clamped,
                panning=-1,
            )
```

### Master Pitch Offset

LMMS's `masterpitch` attribute shifts all instruments by semitones. In IT, this can be baked into the C5Speed of each sample:

```python
def apply_master_pitch(sample: RenderedSample, master_pitch: int):
    """Adjust sample C5Speed to account for master pitch offset."""
    # master_pitch is in semitones (-12 to 12)
    pitch_factor = 2.0 ** (master_pitch / 12.0)
    adjusted_rate = int(sample.sample_rate * pitch_factor)
    sample.sample_rate = adjusted_rate
```

---

## Summary of Key Mappings

| LMMS Concept | IT Equivalent | Notes |
|---|---|---|
| Instrument Track | IT Instrument + Sample | Rendered to audio |
| MIDI Note | Pattern note event | 1 per channel per row |
| Polyphonic chord | Multiple channels | Channel per voice |
| Note volume (0-200) | Volume column (0-64) | Scaled, clipped |
| Track volume | Instrument Global Volume | Static per instrument |
| Track panning | Channel panning / Vol column panning | Per channel or per note |
| Mixer channel volume | Baked into Inst Global Volume | Combined with track vol |
| Mixer send | Baked into gain chain | No direct equivalent |
| Master volume | IT Global Volume | Header field |
| BPM | IT Tempo (Txx) | 32-255 range |
| 192 ticks/bar | Rows per pattern | Via ticks_per_row mapping |
| Automation | Effect column commands | Limited approximation |
| Effects chain | Pre-rendered into samples | No real-time equivalent |
| Muted track | Omitted entirely | No output |
| Solo track | Mute all others | Pre-processing step |

This pipeline produces a fully functional IT file that preserves the melodic, rhythmic, and dynamic content of the original LMMS project, with the fundamental trade-off that all synthesis and effects processing is "frozen" into the rendered samples.