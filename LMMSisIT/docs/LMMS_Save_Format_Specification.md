# LMMS Project File Format Specification

## Overview

LMMS (Linux Multimedia Studio) uses two primary file formats for saving projects:

- **`.mmp`** - Uncompressed XML project file (plain text, human-readable)
- **`.mmpz`** - Compressed project file (zlib-compressed XML)

Additional related formats:
- **`.mpt`** - Project template (same format as `.mmp`/`.mmpz`)
- **`.xpf`** - Instrument track preset (XML-based)
- **`.xpt`/`.xptz`** - MIDI clip presets (uncompressed/compressed)

---

## File Structure

### Compression (.mmpz format)

`.mmpz` files are compressed using Qt's `qCompress()` function, which applies zlib compression. The file reading process:

1. Read raw bytes from file
2. Apply Qt's `qUncompress()` to decompress
3. Parse resulting UTF-8 XML data

```cpp
// From DataFile.cpp
QByteArray uncompressed = qUncompress(_data);
// Then parse as XML
```

### XML Document Structure

The root element is `<lmms-project>` with the following structure:

```xml
<?xml version="1.0"?>
<lmms-project 
    version="27" 
    type="song" 
    creator="LMMS" 
    creatorversion="1.3.0-alpha.1.590+g4522c9b9b"
    creatorplatform="winnt"
    creatorplatformtype="windows">
  <head>
    <!-- Project metadata -->
  </head>
  <song>
    <!-- Main project content -->
  </song>
</lmms-project>
```

### Root Element Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `version` | unsigned int | File format version (used for upgrade routines). Current version is 27. |
| `type` | string | Content type: `song`, `songtemplate`, `instrumenttracksettings`, `dnddata`, `clipboard-data`, `journaldata`, `effectsettings`, `midiclip` |
| `creator` | string | Always "LMMS" |
| `creatorversion` | string | LMMS version that created the file (e.g., "1.3.0-alpha.1.590+g4522c9b9b") |
| `creatorplatform` | string | Kernel type: "winnt", "linux", "darwin" |
| `creatorplatformtype` | string | OS product type: "windows", "ubuntu", "arch", "macos", etc. |

---

## Head Section

The `<head>` element contains project-wide settings:

```xml
<head 
    bpm="140" 
    timesig_numerator="4" 
    timesig_denominator="4" 
    mastervol="100" 
    masterpitch="0">
</head>
```

### Head Attributes

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `bpm` | int | 140 | 10-999 | Beats per minute (tempo) |
| `timesig_numerator` | int | 4 | - | Time signature numerator (beats per bar) |
| `timesig_denominator` | int | 4 | - | Time signature denominator (beat unit) |
| `mastervol` | int | 100 | 0-200 | Master volume percentage |
| `masterpitch` | int | 0 | -12 to 12 | Master pitch offset in semitones |

---

## Song Section

The `<song>` element is the main container for project content:

```xml
<song>
  <trackcontainer>
    <!-- Tracks go here -->
  </trackcontainer>
  <mixer>
    <!-- Mixer/FX channels -->
  </mixer>
  <controllers>
    <!-- LFO, Peak controllers, etc. -->
  </controllers>
  <scales>
    <!-- Microtuning scales -->
  </scales>
  <keymaps>
    <!-- Keyboard mappings -->
  </keymaps>
  <timeline>
    <!-- Timeline state (loop points, etc.) -->
  </timeline>
  <pianoroll>
    <!-- Piano roll editor state -->
  </pianoroll>
  <automationeditor>
    <!-- Automation editor state -->
  </automationeditor>
  <projectnotes>
    <!-- User notes -->
  </projectnotes>
</song>
```

---

## Track System

### Track Container

```xml
<trackcontainer>
  <track type="0" name="TripleOscillator" muted="0" solo="0" mutedBeforeSolo="0" trackheight="32">
    <!-- Track-specific content -->
  </track>
  <track type="1" name="Beat/Bassline 1" muted="0" solo="0">
    <!-- Pattern track content -->
  </track>
</trackcontainer>
```

### Track Types

| Type Value | Enum | Description |
|------------|------|-------------|
| 0 | Instrument | Instrument track (synths, samplers, etc.) |
| 1 | Pattern | Pattern/Beat-Bassline track |
| 2 | Sample | Sample track (audio files on timeline) |
| 5 | Automation | Automation track |
| 6 | HiddenAutomation | Hidden automation track (legacy) |

### Track Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | int | Track type (see table above) |
| `name` | string | Track display name |
| `muted` | bool | Whether track is muted |
| `solo` | bool | Whether track is soloed |
| `mutedBeforeSolo` | bool | Mute state before solo was activated |
| `trackheight` | int | Track height in pixels (minimum 32) |
| `color` | string | Optional: Track color as hex (e.g., "#ff5500") |

---

## Instrument Tracks

Instrument tracks contain both the instrument settings and MIDI clips:

```xml
<track type="0" name="Synth" muted="0" solo="0">
  <instrumenttrack 
      vol="100" 
      pan="0" 
      pitch="0" 
      pitchrange="1" 
      mixch="0" 
      basenote="69" 
      firstkey="0" 
      lastkey="127"
      usemasterpitch="1">
    <instrument name="tripleoscillator">
      <tripleoscillator 
          useWaveTable1="0" 
          wavefile1="" 
          vol1="33" 
          pan1="0" 
          coarse1="0" 
          fine1="0" 
          phoffset1="0" 
          stphdetun1="0">
        <!-- Oscillator 1 settings -->
      </tripleoscillator>
      <!-- More oscillators... -->
    </instrument>
    <eldata fcut="14000" fres="0.5" ftype="0" fwet="0">
      <!-- Envelope/filter data -->
    </eldata>
    <chordcreator chord-enabled="0" chord="0" chordrange="1">
      <!-- Chord settings -->
    </chordcreator>
    <arpeggiator arp-enabled="0" arpmode="0" arpgate="100" arpsyncmode="0">
      <!-- Arpeggiator settings -->
    </arpeggiator>
    <fxchain enabled="0" numofeffects="0">
      <!-- Effect chain -->
    </fxchain>
    <midiport inputchannel="0" outputchannel="0" fixedoutputvelocity="-1">
      <!-- MIDI port configuration -->
    </midiport>
  </instrumenttrack>
  <midiclip pos="0" len="192" name="Pattern 1" muted="0">
    <!-- MIDI notes -->
  </midiclip>
</track>
```

### Instrument Track Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `vol` | float | 100 | Volume (0-200) |
| `pan` | float | 0 | Panning (-100 to 100) |
| `pitch` | float | 0 | Pitch offset in cents |
| `pitchrange` | int | 1 | Pitch bend range in semitones |
| `mixch` | int | 0 | Mixer channel assignment |
| `basenote` | int | 69 | Base note (A4 = 69 in MIDI) |
| `firstkey` | int | 0 | Lowest playable key |
| `lastkey` | int | 127 | Highest playable key |
| `usemasterpitch` | bool | 1 | Whether to follow master pitch |

---

## MIDI Clips and Notes

### MIDI Clip Structure

```xml
<midiclip pos="0" len="192" name="Melody" muted="0" steps="16" type="1">
  <note pos="0" len="48" key="69" vol="100" pan="0"/>
  <note pos="48" len="48" key="71" vol="100" pan="0"/>
  <note pos="96" len="96" key="72" vol="100" pan="0">
    <detuning info="1" len="96">
      <!-- Per-note automation for detuning -->
    </detuning>
  </note>
</midiclip>
```

### MIDI Clip Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `pos` | int | Start position in ticks |
| `len` | int | Length in ticks |
| `name` | string | Clip name (optional) |
| `muted` | bool | Whether clip is muted |
| `steps` | int | Number of steps (for beat clips) |
| `type` | int | 0=BeatClip, 1=MelodyClip |

### Note Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `pos` | int | 0 | Position within clip in ticks |
| `len` | int | - | Length in ticks (negative for step notes) |
| `key` | int | 69 | MIDI key number (0-127) |
| `vol` | int | 100 | Velocity/volume (0-200) |
| `pan` | int | 0 | Panning (-100 to 100) |
| `type` | int | 0 | 0=Regular, 1=Step note |

### Time System

LMMS uses a tick-based timing system:

- **DefaultTicksPerBar** = 192 ticks (at 4/4 time signature)
- Ticks per bar = `(timesig_numerator * 48 * 4) / timesig_denominator`
- Position values are in ticks relative to parent container

---

## Automation Clips

Automation clips store automated parameter values:

```xml
<automationclip pos="0" len="192" name="Volume" muted="0" prog="1" tens="1">
  <time pos="0" outValue="0.5"/>
  <time pos="96" outValue="1.0"/>
  <time pos="192" outValue="0.5"/>
  <object id="12345"/>
</automationclip>
```

### Automation Clip Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `pos` | int | Start position in ticks |
| `len` | int | Length in ticks |
| `name` | string | Clip name |
| `muted` | bool | Whether clip is muted |
| `prog` | int | Progression type: 0=Discrete, 1=Linear, 2=CubicHermite |
| `tens` | float | Tension for cubic interpolation (0-1) |

### Time Node Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `pos` | int | Position in ticks within the clip |
| `outValue` | float | Automation value at this position |
| `inValue` | float | Optional: Different in-value for non-linear curves |
| `inTangent` | float | Optional: In-tangent for cubic interpolation |
| `outTangent` | float | Optional: Out-tangent for cubic interpolation |
| `lockedTangents` | bool | Optional: Whether tangents are locked together |

### Object References

The `<object id="..."/>` element references the AutomatableModel being controlled by its journal ID.

---

## Sample Tracks

Sample tracks are a track type (type 2) designed for arranging audio samples directly on the timeline. Unlike instrument tracks, sample tracks play audio files directly without MIDI note sequencing.

### Sample Track Structure

```xml
<track type="2" name="Sample Track" muted="0" solo="0" trackheight="32">
  <sampletrack vol="100" pan="0" mixch="0">
    <fxchain enabled="0" numofeffects="0">
      <!-- Effects chain -->
    </fxchain>
  </sampletrack>
  <sampleclip pos="0" len="22050" muted="0" 
              src="factorysample:drums/loops/beat01.ogg"
              off="0" autoresize="1" sample_rate="44100"/>
  <sampleclip pos="384" len="192" muted="0" src="usersample:my_sample.wav"/>
</track>
```

### Sample Track Element (`<sampletrack>`)

The `<sampletrack>` element is a child of the `<track>` element and contains track-specific settings:

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `vol` | float | 100 | 0-200 | Track volume percentage |
| `pan` | float | 0 | -100 to 100 | Panning (left to right) |
| `mixch` | int | 0 | 0+ | Mixer channel assignment (0 = Master) |

#### Effect Chain

Sample tracks can have an effect chain:

```xml
<sampletrack vol="100" pan="0" mixch="0">
  <fxchain enabled="1" numofeffects="1">
    <effect name="ladspaeffect" gate="0" wet="1" autoquit="1">
      <!-- Effect configuration -->
    </effect>
  </fxchain>
</sampletrack>
```

### Sample Clip Element (`<sampleclip>`)

Sample clips are children of the track element and represent individual audio samples placed on the timeline:

```xml
<sampleclip pos="0" len="22050" muted="0" 
            src="factorysample:drums/kick.wav"
            off="0" autoresize="1" sample_rate="44100"
            color="#ff5500" reversed="true"/>
```

### Sample Clip Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `pos` | int | 0 | Start position in ticks |
| `len` | int | - | Length in ticks |
| `muted` | bool | 0 | Whether clip is muted |
| `src` | string | - | Path to audio file (with optional prefix) |
| `off` | int | 0 | Start time offset in ticks |
| `autoresize` | bool | 1 | Whether clip auto-resizes to sample length |
| `data` | string | - | Base64-encoded sample data (if no file) |
| `sample_rate` | int | - | Sample rate of embedded sample (with `data`) |
| `color` | string | - | Optional clip color as hex (e.g., "#ff5500") |
| `reversed` | bool | false | Whether the sample is played in reverse |

### Path Prefixes

File paths in `src` can use special prefixes for portability:

| Prefix | Description |
|--------|-------------|
| `factorysample:` | Factory samples directory |
| `usersample:` | User samples directory |
| `factorypreset:` | Factory presets directory |
| `userpreset:` | User presets directory |
| `local:` | Project bundle local resources |

### Embedded Sample Data

If no `src` file is available, samples can be embedded directly using Base64-encoded data:

```xml
<sampleclip pos="0" len="192" muted="0" 
            data="UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="
            sample_rate="44100"/>
```

The `data` attribute contains Base64-encoded audio sample data. The `sample_rate` attribute specifies the original sample rate for proper playback.

### Reversed Playback

When `reversed="true"` is set, the sample plays backwards:

```xml
<sampleclip pos="0" len="22050" src="usersample:cymbal.wav" reversed="true"/>
```

### Time Offset

The `off` attribute provides a start time offset in ticks, allowing the clip to start playing from a point within the sample:

```xml
<sampleclip pos="0" len="192" src="usersample:loop.wav" off="48"/>
```

This starts playback 48 ticks into the sample.

### Auto-Resize Behavior

When `autoresize="1"` (default):
- The clip length automatically adjusts to match the sample duration
- Changes when BPM changes (since ticks represent time differently at different tempos)
- Manual resizing disables auto-resize

When `autoresize="0"`:
- The clip maintains its manually set length
- The sample may be truncated or may end before the clip ends

### Sample Length Calculation

The clip length in ticks is calculated from the sample's frame count:

```cpp
TimePos SampleClip::sampleLength() const
{
    return static_cast<int>(m_sample.sampleSize() / Engine::framesPerTick(m_sample.sampleRate()));
}
```

Where `framesPerTick` depends on the current tempo:
```cpp
framesPerTick = sampleRate * 60.0f * 4 / DefaultTicksPerBar / tempo;
```

### Complete Sample Track Example

```xml
<track type="2" name="Vocals" muted="0" solo="0" trackheight="64">
  <sampletrack vol="85" pan="0" mixch="1">
    <fxchain enabled="1" numofeffects="2">
      <effect name="ladspaeffect" gate="0" wet="0.8" autoquit="1">
        <ladspacontrols>
          <port01 data="0.5"/>
          <port02 data="0.3"/>
        </ladspacontrols>
        <key>
          <attribute name="plugin" value="Calf Reverb"/>
          <attribute name="file" value="calf"/>
        </key>
      </effect>
      <effect name="ladspaeffect" gate="0" wet="0.5" autoquit="1">
        <ladspacontrols>
          <port01 data="0.7"/>
        </ladspacontrols>
        <key>
          <attribute name="plugin" value="Calf Compressor"/>
          <attribute name="file" value="calf"/>
        </key>
      </effect>
    </fxchain>
  </sampletrack>
  <sampleclip pos="0" len="1536" muted="0" 
              src="usersample:vocals/verse1.wav" 
              autoresize="1"/>
  <sampleclip pos="1536" len="1536" muted="0" 
              src="usersample:vocals/chorus.wav" 
              autoresize="1"/>
  <sampleclip pos="3072" len="768" muted="1" 
              src="usersample:vocals/bridge.wav" 
              autoresize="1" color="#ff0000"/>
  <sampleclip pos="3840" len="1536" muted="0" 
              src="usersample:vocals/outro.wav" 
              reversed="true" autoresize="1"/>
</track>
```

### Playback Behavior

Sample tracks handle playback differently from instrument tracks:

1. **Direct Audio Playback**: Samples play directly without MIDI triggering
2. **Position-Based**: Playback is based on the timeline position, not note events
3. **Sample Rate Handling**: Sample rate conversion is applied automatically if the sample's rate differs from the project rate
4. **Real-Time Stretching**: When BPM changes, sample clips adjust their tick length while maintaining audio duration

### Recording

Sample tracks support recording audio input:

```xml
<sampleclip pos="0" len="192" muted="0" record="1"/>
```

The `record` attribute (BoolModel) enables recording mode on the clip.

### Mixer Routing

Sample tracks route to the mixer via the `mixch` attribute:

- `mixch="0"` routes directly to the Master channel
- `mixch="1"` routes to FX channel 1
- Higher values route to the corresponding FX channel

The routing occurs after the track's volume, panning, and effect chain processing.

### Sample Track vs AudioFileProcessor

Sample tracks and the AudioFileProcessor instrument serve different purposes:

| Feature | Sample Track | AudioFileProcessor |
|---------|--------------|-------------------|
| Triggering | Timeline position | MIDI notes |
| Pitch | Original pitch | Follows MIDI key |
| Time stretching | No (unless BPM changes) | Yes (follows note length) |
| Multiple instances | Multiple clips per track | One sample per instance |
| Use case | Arranging recordings | Sampling/beat making |

---

## Mixer (FX Channels)

```xml
<mixer>
  <mixerchannel num="0" name="Master" muted="0" solo="0" volume="1">
    <fxchain enabled="0" numofeffects="0">
      <!-- Effects -->
    </fxchain>
    <send channel="1" amount="0.5"/>
  </mixerchannel>
  <mixerchannel num="1" name="FX 1" muted="0" solo="0" volume="1">
    <fxchain enabled="1" numofeffects="1">
      <effect name="ladspaeffect" gate="0" wet="1" autoquit="1">
        <ladspacontrols>
          <port01 data="0.5"/>
          <port02 data="1.0" link="1"/>
        </ladspacontrols>
        <key>
          <attribute name="plugin" value="Calf Reverb"/>
          <attribute name="file" value="calf"/>
        </key>
      </effect>
    </fxchain>
  </mixerchannel>
</mixer>
```

### Mixer Channel Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `num` | int | Channel index (0 = Master) |
| `name` | string | Channel name |
| `muted` | bool | Whether channel is muted |
| `solo` | bool | Whether channel is soloed |
| `volume` | float | Channel volume (0-2, 1=100%) |
| `color` | string | Optional: Channel color as hex |

### Send Element

```xml
<send channel="1" amount="0.5"/>
```
Defines a send from this channel to another channel with specified amount.

---

## Effects

### Effect Structure

```xml
<effect name="ladspaeffect" gate="0" wet="1" autoquit="1">
  <ladspacontrols>
    <port01 data="0.5"/>
    <port02 data="1.0" link="1"/>
    <port03 data="0.5" scale_type="log"/>
  </ladspacontrols>
  <key>
    <attribute name="plugin" value="Calf Reverb"/>
    <attribute name="file" value="veal"/>
  </key>
</effect>
```

### Effect Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | string | Effect plugin identifier |
| `gate` | bool | Auto-quit enabled |
| `wet` | float | Wet/dry mix (0-1) |
| `autoquit` | float | Auto-quit decay time in ms |

### LADSPA Port Controls

```xml
<port01 data="0.5" link="1"/>
```

Port names are `port` followed by zero-padded number (e.g., `port01`, `port02`, etc.)

| Attribute | Type | Description |
|-----------|------|-------------|
| `data` | float | Current value |
| `link` | bool | Optional: Link to another control |
| `scale_type` | string | Optional: "log" for logarithmic scaling |

---

## Controllers

Controllers provide real-time parameter automation sources:

```xml
<controllers>
  <lfocontroller wave="0" speed="0.1" amount="1" phase="0" 
                 multiplier="1" muted="0">
    <object id="12345"/>
  </lfocontroller>
  <peakcontroller attack="0.1" decay="0.5" amount="1" muted="0">
    <object id="67890"/>
  </peakcontroller>
</controllers>
```

### LFO Controller Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `wave` | int | Waveform: 0=Sine, 1=Triangle, 2=Saw, 3=Square, 4=Random, 5=Sample&Hold |
| `speed` | float | LFO speed (Hz or tempo-synced) |
| `amount` | float | Modulation amount |
| `phase` | float | Phase offset (0-360) |
| `multiplier` | int | Speed multiplier |
| `muted` | bool | Whether controller is muted |

### Peak Controller Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `attack` | float | Attack time |
| `decay` | float | Decay time |
| `amount` | float | Modulation amount |
| `muted` | bool | Whether controller is muted |

---

## Pattern Tracks (Beat/Bassline Editor)

Pattern tracks contain references to patterns in the Pattern Store:

```xml
<track type="1" name="Pattern 1" muted="0" solo="0">
  <patterntrack>
    <!-- Pattern-specific settings -->
  </patterntrack>
  <patternclip pos="0" len="192" name="" muted="0"/>
  <patternclip pos="192" len="192" name="" muted="0"/>
</track>
```

---

## Timeline and Loop Points

```xml
<timeline loopEnabled="1" loopStartPos="0" loopEndPos="768" 
          stopBehaviour="0" playStartPosition="0">
</timeline>
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `loopEnabled` | bool | Whether loop is active |
| `loopStartPos` | int | Loop start position in ticks |
| `loopEndPos` | int | Loop end position in ticks |
| `stopBehaviour` | int | 0=BackToZero, 1=BackToStart, 2=KeepPosition |
| `playStartPosition` | int | Position where playback started |

---

## Scales and Keymaps (Microtuning)

### Scales

```xml
<scales>
  <scale name="12-TET" enabled="1">
    <note key="0" cents="0"/>
    <note key="1" cents="100"/>
    <!-- ... -->
  </scale>
</scales>
```

### Keymaps

```xml
<keymaps>
  <keymap name="Standard" enabled="1">
    <key note="0" destKey="0"/>
    <key note="1" destKey="1"/>
    <!-- ... -->
  </keymap>
</keymaps>
```

---

## Project Notes

```xml
<projectnotes>
  <![CDATA[
    User's project notes text here...
  ]]>
</projectnotes>
```

---

## Piano Roll and Automation Editor State

Editor UI states are saved for session restoration:

```xml
<pianoroll scrollx="0" scrolly="60" zoomx="1" zoomy="1" 
           currentKey="69" lenOfPattern="192"/>
<automationeditor scrollx="0" zoomx="1" zoomy="1"/>
```

---

## File Format Versioning

LMMS maintains backward compatibility through upgrade routines. The `version` attribute in the root element determines which upgrade methods to apply:

### Version History

Current file version is **27**. Key versions include:

| Version | Release | Notes |
|---------|---------|-------|
| 0 | Pre-0.2.1 | Initial format |
| 1-3 | 0.2.1 | Early development |
| 4-11 | 0.3.0 - 0.4.0-rc2 | Major restructuring |
| 12-17 | 1.0.0 - 1.2.0-rc3 | Feature additions |
| 18+ | 1.3.0+ | Modern format |

### Upgrade System

When loading older files, LMMS automatically applies upgrade routines:

```cpp
// From DataFile.cpp
void upgrade();
void upgrade_0_2_1_20070501();
void upgrade_0_2_1_20070508();
// ... etc for each version
```

---

## Data Types Reference

### Boolean Values

Boolean attributes use integer representation:
- `0` = false
- `1` = true

### Float Values

Float values use locale-independent string representation (period as decimal separator).

### Time Values

All time values are in **ticks**:
- 192 ticks = 1 bar (at 4/4 time signature)
- Position = ticks from start
- Length = ticks duration

### MIDI Values

| Parameter | Range |
|-----------|-------|
| Key | 0-127 (MIDI standard) |
| Velocity/Volume | 0-200 (LMMS extended) |
| Panning | -100 to 100 |
| Base Note | 0-127 (69 = A4 = 440Hz) |

---

## Path Handling

LMMS uses a path utility system for portable project files:

### Path Bases

```cpp
enum class Base {
    FactoryDir,      // LMMS installation directory
    UserDir,         // User's LMMS directory
    FactorySample,   // Factory samples
    UserSample,      // User samples
    FactoryPreset,   // Factory presets
    UserPreset,      // User presets
    LocalDir         // Project bundle local directory
};
```

### Path Format in Files

Paths are stored with prefixes:
```
factorysample:drums/kick.wav
usersample:my_samples/recording.wav
userpreset:my_presets/synth.xpf
local:resources/sample.wav
```

---

## Security Considerations

### Local Path Protection

LMMS blocks loading projects with suspicious `local:` paths in plugin elements to prevent code injection:

```cpp
bool DataFile::hasLocalPlugins(QDomElement parent, bool firstCall) const;
```

Only `sampleclip` and `audiofileprocessor` elements are allowed to have `local:` paths.

---

## Project Bundles

When saving with "Save as Bundle" option:

1. A directory is created with project name
2. A `resources/` subdirectory contains all external files
3. All paths are converted to `local:` references
4. The project file is saved inside the bundle directory

---

## Example Minimal Project

```xml
<?xml version="1.0"?>
<lmms-project version="27" type="song" creator="LMMS" 
              creatorversion="1.3.0">
  <head bpm="140" timesig_numerator="4" timesig_denominator="4" 
        mastervol="100" masterpitch="0"/>
  <song>
    <trackcontainer>
      <track type="0" name="TripleOscillator" muted="0" solo="0">
        <instrumenttrack vol="100" pan="0" mixch="0">
          <instrument name="tripleoscillator">
            <tripleoscillator/>
          </instrument>
        </instrumenttrack>
        <midiclip pos="0" len="192" muted="0">
          <note pos="0" len="48" key="69" vol="100"/>
        </midiclip>
      </track>
    </trackcontainer>
    <mixer>
      <mixerchannel num="0" name="Master" volume="1"/>
    </mixer>
    <timeline loopEnabled="0"/>
  </song>
</lmms-project>
```

---

## Appendix: Element Hierarchy

```
lmms-project
├── head
└── song
    ├── trackcontainer
    │   └── track (multiple)
    │       ├── instrumenttrack | sampletrack | patterntrack | automationtrack
    │       └── midiclip | sampleclip | patternclip | automationclip (multiple)
    │           ├── note (multiple, in midiclip)
    │           ├── time (multiple, in automationclip)
    │           └── object (multiple, in automationclip)
    ├── mixer
    │   └── mixerchannel (multiple)
    │       ├── fxchain
    │       │   └── effect (multiple)
    │       │       ├── ladspacontrols | lv2controls
    │       │       └── key
    │       └── send (multiple)
    ├── controllers
    │   └── lfocontroller | peakcontroller | controller (multiple)
    ├── scales
    │   └── scale (multiple)
    ├── keymaps
    │   └── keymap (multiple)
    ├── timeline
    ├── pianoroll
    ├── automationeditor
    └── projectnotes
```

---

## VeSTige (VST Plugin Hosting)

VeSTige is LMMS's VST plugin host instrument that allows loading and using VST instrument plugins (VSTi) within LMMS projects.

### VeSTige Instrument Structure

```xml
<track type="0" name="VST Instrument" muted="0" solo="0">
  <instrumenttrack vol="100" pan="0" mixch="0">
    <instrument name="VeSTige">
      <VeSTige plugin="path/to/plugin.dll" 
               guivisible="1">
        <vstplugin program="0" 
                   numparams="128" 
                   chunk="base64encodeddata..."
                   param0="0:ParamName:0.500000"
                   param1="1:Cutoff:0.750000"
                   ...
                   param127="127:Volume:1.000000"/>
        <param0 id="12345" value="0.5"/>
        <param1 id="12346" value="0.75"/>
      </VeSTige>
    </instrument>
  </instrumenttrack>
  <midiclip pos="0" len="192" muted="0">
    <!-- MIDI notes for the VST instrument -->
  </midiclip>
</track>
```

### VeSTige Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `plugin` | string | Path to VST plugin DLL/SO file (relative or absolute) |
| `guivisible` | int | Whether the VST GUI window is visible (0=hidden, 1=visible) |

### VST Plugin Element Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `program` | int | Current program/preset index |
| `numparams` | int | Number of parameters (only if no chunk) |
| `chunk` | string | Base64-encoded plugin state chunk (if supported) |

### Parameter Storage

VST plugins can store their state in two ways:

#### 1. Chunk-Based Storage (Preferred)

If the VST plugin supports chunk storage (`effFlagsProgramChunks`), the entire plugin state is serialized as a binary chunk and encoded in Base64:

```xml
<vstplugin program="0" chunk="VGhpcyBpcyBiYXNlNjQgZW5jb2RlZCBkYXRhLi4u"/>
```

The chunk contains:
- All parameter values
- Plugin-specific internal state
- Preset data

#### 2. Parameter Dump (Fallback)

If the plugin doesn't support chunks, individual parameters are stored:

```xml
<vstplugin program="0" numparams="128">
  <param0 value="0.500000"/>
  <param1 value="0.750000"/>
  ...
</vstplugin>
```

Each parameter follows the format:
```
paramN="index:name:value"
```

Where:
- `index` = Parameter index (0-based)
- `name` = Parameter short label/name
- `value` = Parameter value (0.0 to 1.0, normalized)

### Automated VST Parameters

When VST parameters are automated in LMMS, they create FloatModel entries:

```xml
<VeSTige plugin="synth.dll">
  <vstplugin program="0" chunk="...">
    <param0 id="12345" value="0.5"/>
    <param1 id="12346" value="0.75"/>
  </vstplugin>
</VeSTige>
```

The `id` attribute references the AutomatableModel for automation tracking. Only automated or controller-connected parameters have these saved.

### VST Preset Files

VeSTige can load external VST preset files:

| Format | Extension | Description |
|--------|-----------|-------------|
| FXP | `.fxp` | Single program preset |
| FXB | `.fxb` | Bank preset (multiple programs) |

Preset files use a proprietary format defined by Steinberg's VST SDK.

### Plugin DLL Detection

LMMS detects the plugin architecture to load the correct host:

| Architecture | Detection | Host Plugin |
|--------------|-----------|-------------|
| Windows 32-bit | PE machine type `0x14c` | RemoteVstPlugin32 |
| Windows 64-bit | PE machine type `0x8664` | RemoteVstPlugin64 |
| Linux 64-bit | `.so` extension | NativeLinuxRemoteVstPlugin |

### VST Plugin Communication

VeSTige uses a remote plugin architecture:

1. **Host Process** - LMMS main application
2. **Remote Plugin Process** - Separate process hosting the VST
3. **Communication** - IPC via shared memory and message passing

This architecture allows:
- Running 32-bit plugins on 64-bit LMMS (on Windows)
- Plugin isolation (crashes don't affect LMMS)
- Cross-platform VST support via Wine (Linux)

### VST Parameter Automation

Each VST parameter can be controlled via:

1. **LMMS Automation Clips** - Standard LMMS automation
2. **MIDI CC** - Via MIDI controller input
3. **LFO/Peak Controller** - LMMS controller connections

The parameter dump format:
```
paramN = "index:label:value"
```

Example from `parameterDump()`:
```cpp
m_parameterDump["param0"] = "0:Cutoff:0.750000"
m_parameterDump["param1"] = "1:Resonance:0.500000"
```

### GUI Embedding Methods

VST plugin GUIs can be embedded using different methods (configured via `vstembedmethod`):

| Method | Platform | Description |
|--------|----------|-------------|
| `qt` | All | Qt window container (recommended) |
| `win32` | Windows | Native Windows embedding |
| `xembed` | Linux | X11 embed container (Qt5 only) |
| `none` | All | Detached window |
| `headless` | All | No GUI (for rendering) |

### Example Complete VeSTige Track

```xml
<track type="0" name="Serum" muted="0" solo="0" trackheight="64">
  <instrumenttrack vol="85" pan="0" pitch="0" pitchrange="2" 
                   mixch="1" basenote="69" usemasterpitch="1">
    <instrument name="VeSTige">
      <VeSTige plugin="C:/VST/Serum_x64.dll" guivisible="1">
        <vstplugin program="0" chunk="VGhpcyBpcyBhIHNlcmlhbGl6ZWQgU2VydW0gc3RhdGUuLi4="/>
        <param0 id="54321" value="0.65"/>
        <param24 id="54322" value="0.8"/>
      </VeSTige>
    </instrument>
    <eldata fcut="14000" fres="0.5" ftype="0" fwet="0"/>
    <chordcreator chord-enabled="0"/>
    <arpeggiator arp-enabled="0"/>
    <fxchain enabled="0" numofeffects="0"/>
  </instrumenttrack>
  <midiclip pos="0" len="768" name="Main Lead" muted="0" type="1">
    <note pos="0" len="192" key="60" vol="100" pan="0"/>
    <note pos="192" len="192" key="64" vol="100" pan="0"/>
    <note pos="384" len="192" key="67" vol="100" pan="0"/>
    <note pos="576" len="192" key="72" vol="100" pan="0"/>
  </midiclip>
</track>
```

## AudioFileProcessor (Sampler Instrument)

AudioFileProcessor is LMMS's built-in sampler instrument that allows loading and playing audio files with various playback options.

### AudioFileProcessor Structure

```xml
<track type="0" name="Sample Instrument" muted="0" solo="0">
  <instrumenttrack vol="100" pan="0" mixch="0" basenote="69">
    <instrument name="AudioFileProcessor">
      <AudioFileProcessor 
          src="factorysample:drums/kick.wav"
          amp="100"
          reversed="0"
          looped="0"
          sframe="0"
          eframe="1"
          lframe="0"
          stutter="0"
          interp="1"/>
    </instrument>
  </instrumenttrack>
  <midiclip pos="0" len="192" muted="0">
    <note pos="0" len="48" key="69" vol="100"/>
  </midiclip>
</track>
```

### AudioFileProcessor Attributes

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `src` | string | - | - | Path to audio sample file |
| `sampledata` | string | - | - | Base64-encoded sample data (if no file) |
| `amp` | float | 100 | 0-500 | Amplification percentage |
| `reversed` | bool | 0 | 0-1 | Reverse sample playback |
| `looped` | int | 0 | 0-2 | Loop mode (see table below) |
| `sframe` | float | 0 | 0-1 | Start point (normalized 0-1) |
| `eframe` | float | 1 | 0-1 | End point (normalized 0-1) |
| `lframe` | float | 0 | 0-1 | Loop point (normalized 0-1) |
| `stutter` | bool | 0 | 0-1 | Stutter mode (continuous playback) |
| `interp` | int | 1 | 0-2 | Interpolation mode (see table below) |

### Loop Modes

| Value | Mode | Description |
|-------|------|-------------|
| 0 | Off | No looping, play once |
| 1 | On | Loop between loop point and end point |
| 2 | PingPong | Alternate forward/reverse between loop and end points |

### Interpolation Modes

| Value | Mode | Description |
|-------|------|-------------|
| 0 | None | Zero-Order Hold (nearest neighbor) |
| 1 | Linear | Linear interpolation (default) |
| 2 | Sinc | Sinc interpolation (highest quality) |

### Sample Point System

Sample points use normalized values (0.0 to 1.0) representing the position within the sample:

- `sframe` - Where playback begins
- `eframe` - Where playback ends
- `lframe` - Where playback jumps back to when looping

The actual frame is calculated as: `frame_index = normalized_value * total_sample_frames`

### Embedded Sample Data

If no `src` file is available, samples can be embedded directly:

```xml
<AudioFileProcessor 
    sampledata="UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="
    amp="100" looped="0" sframe="0" eframe="1"/>
```

The `sampledata` attribute contains Base64-encoded audio data processed via `SampleBuffer::fromBase64()`.

### Stutter Mode

When `stutter="1"`:
- Sample playback continues across notes
- Each new note resumes from where the previous note left off
- Special "magic key" (frequency < 20Hz) resets playback to start point
- Useful for creating continuous, evolving textures

### Sample File Formats

AudioFileProcessor supports the following formats:

| Format | Extensions |
|--------|------------|
| WAV | `.wav` |
| Ogg Vorbis | `.ogg` |
| Drumsynth | `.ds` |
| Speex | `.spx` |
| AU | `.au` |
| VOC | `.voc` |
| AIFF | `.aif`, `.aiff` |
| FLAC | `.flac` |
| Raw | `.raw` |
| MP3 | `.mp3` (if compiled with support) |

### Example Complete AudioFileProcessor Track

```xml
<track type="0" name="Piano Loop" muted="0" solo="0" trackheight="64">
  <instrumenttrack vol="100" pan="0" pitch="0" pitchrange="1" 
                   mixch="0" basenote="69" usemasterpitch="1">
    <instrument name="AudioFileProcessor">
      <AudioFileProcessor 
          src="usersample:my_samples/piano_loop.wav"
          amp="100"
          reversed="0"
          looped="1"
          sframe="0"
          eframe="1"
          lframe="0.25"
          stutter="0"
          interp="2"/>
    </instrument>
    <eldata fcut="14000" fres="0.5" ftype="0" fwet="0"/>
    <chordcreator chord-enabled="0"/>
    <arpeggiator arp-enabled="0"/>
    <fxchain enabled="0" numofeffects="0"/>
  </instrumenttrack>
  <midiclip pos="0" len="384" name="Pattern" muted="0" type="1">
    <note pos="0" len="192" key="69" vol="100" pan="0"/>
    <note pos="192" len="192" key="72" vol="100" pan="0"/>
  </midiclip>
</track>
```

### Path Handling for Samples

Sample paths use the prefix system:

| Prefix | Example | Description |
|--------|---------|-------------|
| `factorysample:` | `factorysample:drums/kick.wav` | Factory sample library |
| `usersample:` | `usersample:my_kick.wav` | User sample directory |
| `local:` | `local:resources/sample.wav` | Project bundle local |

### Security Note

The `local:` path prefix is explicitly allowed for AudioFileProcessor by the security system to enable project bundles to include embedded samples.

---

## BitInvader (Wavetable Synthesizer)

BitInvader is a customizable wavetable synthesizer that allows users to draw their own waveforms or select from preset shapes.

### BitInvader Structure

```xml
<track type="0" name="BitInvader" muted="0" solo="0">
  <instrumenttrack vol="100" pan="0" mixch="0" basenote="69">
    <instrument name="BitInvader">
      <BitInvader version="0.1" 
                  sampleLength="200" 
                  sampleShape="base64encodedfloatarray..."
                  interpolation="0" 
                  normalize="1"/>
    </instrument>
  </instrumenttrack>
  <midiclip pos="0" len="192" muted="0">
    <note pos="0" len="48" key="69" vol="100"/>
  </midiclip>
</track>
```

### BitInvader Attributes

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `version` | string | "0.1" | - | Plugin version string |
| `sampleLength` | int | 200 | 4-200 | Active wavetable length (number of samples used) |
| `sampleShape` | string | - | - | Base64-encoded float array (200 floats) |
| `interpolation` | bool | 0 | 0-1 | Enable linear interpolation between samples |
| `normalize` | bool | 0 | 0-1 | Normalize waveform to maximum amplitude |

### Wavetable Storage

The waveform is stored as a Base64-encoded array of 200 floating-point values:

```cpp
// Encoding (saveSettings)
QString sampleString;
base64::encode((const char *)m_graph.samples(),
    wavetableSize * sizeof(float), sampleString);
_this.setAttribute("sampleShape", sampleString);

// Decoding (loadSettings)  
int size = 0;
char * dst = 0;
base64::decode(_this.attribute("sampleShape"), &dst, &size);
m_graph.setSamples(reinterpret_cast<float*>(dst));
```

Each float value represents a sample point in the range [-1.0, 1.0].

### Wavetable Size

- **Fixed Size**: Always 200 samples (defined by `wavetableSize` constant)
- **Active Length**: `sampleLength` determines how many samples are actually used (4-200)
- Playback wraps around at the active length, not the full 200

### Interpolation Modes

| Value | Mode | Description |
|-------|------|-------------|
| 0 | Nearest | No interpolation (nearest neighbor) |
| 1 | Linear | Linear interpolation between adjacent samples |

### Normalization

When `normalize="1"`:
- The waveform is scaled so the maximum amplitude reaches ±1.0
- Prevents clipping and ensures consistent volume across different waveforms
- The normalization factor is calculated from the absolute maximum value

### Preset Waveforms

BitInvader provides built-in waveform presets that can be loaded via the UI:

| Button | Waveform | Description |
|--------|----------|-------------|
| Sine | Sine wave | Smooth harmonic oscillator |
| Triangle | Triangle wave | Linear ramp up/down |
| Saw | Sawtooth wave | Linear ramp up with sharp drop |
| Square | Square wave | Alternating high/low values |
| Noise | White noise | Random values |
| User | User file | Load custom waveform from audio file |
| Smooth | - | Apply smoothing filter to current waveform |

### Sound Generation

BitInvader synthesizes sound by:

1. Reading through the wavetable at a rate determined by note frequency
2. Wrapping around when reaching the active length
3. Optionally interpolating between adjacent samples
4. Applying the normalization factor if enabled

```cpp
// Sample step calculation
auto sample_step = static_cast<float>(sample_length / (sample_rate / nph->frequency()));

// With interpolation
const auto nextIndex = currentIndex < sample_length - 1 ? currentIndex + 1 : 0;
return std::lerp(sample_shape[currentIndex], sample_shape[nextIndex], fraction(currentRealIndex));
```

### Example Complete BitInvader Track

```xml
<track type="0" name="Custom Synth" muted="0" solo="0" trackheight="64">
  <instrumenttrack vol="100" pan="0" pitch="0" pitchrange="1" 
                   mixch="0" basenote="69" usemasterpitch="1">
    <instrument name="BitInvader">
      <BitInvader version="0.1" 
                  sampleLength="100" 
                  sampleShape="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA..."
                  interpolation="1" 
                  normalize="1"/>
    </instrument>
    <eldata fcut="14000" fres="0.5" ftype="0" fwet="0"/>
    <chordcreator chord-enabled="0"/>
    <arpeggiator arp-enabled="0"/>
    <fxchain enabled="0" numofeffects="0"/>
  </instrumenttrack>
  <midiclip pos="0" len="384" name="Bass Line" muted="0" type="1">
    <note pos="0" len="192" key="45" vol="100" pan="0"/>
    <note pos="192" len="192" key="57" vol="100" pan="0"/>
  </midiclip>
</track>
```

### Technical Details

- **Sample Rate Independence**: The wavetable is played back at a rate proportional to the note frequency
- **Phase Continuity**: The phase wraps smoothly at the wavetable boundary
- **Release Time**: Default release time is 1.5ms for quick note endings

---

## FreeBoy (Game Boy APU Emulator)

FreeBoy is an emulation of the Nintendo Game Boy's Audio Processing Unit (APU), providing authentic 8-bit chiptune sounds.

### FreeBoy Structure

```xml
<track type="0" name="FreeBoy" muted="0" solo="0">
  <instrumenttrack vol="100" pan="0" mixch="0" basenote="69">
    <instrument name="FreeBoy">
      <FreeBoy st="4" sd="0" srs="4" ch1wpd="2" ch1vol="15" ch1vsd="0" ch1ssl="0"
                ch2wpd="2" ch2vol="15" ch2vsd="0" ch2ssl="0"
                ch3vol="3"
                ch4vol="15" ch4vsd="0" ch4ssl="0" srw="0"
                so1vol="7" so2vol="7"
                ch1so1="1" ch2so1="1" ch3so1="1" ch4so1="0"
                ch1so2="1" ch2so2="1" ch3so2="1" ch4so2="0"
                Treble="-20" Bass="461"
                sampleShape="base64encodedfloatarray..."/>
    </instrument>
  </instrumenttrack>
  <midiclip pos="0" len="192" muted="0">
    <note pos="0" len="48" key="69" vol="100"/>
  </midiclip>
</track>
```

### FreeBoy Attributes

#### Channel 1 (Square with Sweep)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `st` | int | 4 | 0-7 | Sweep time |
| `sd` | bool | 0 | 0-1 | Sweep direction (0=up, 1=down) |
| `srs` | int | 4 | 0-7 | Sweep rate shift amount |
| `ch1wpd` | int | 2 | 0-3 | Wave pattern duty cycle |
| `ch1vol` | int | 15 | 0-15 | Channel 1 volume |
| `ch1vsd` | bool | 0 | 0-1 | Volume sweep direction |
| `ch1ssl` | int | 0 | 0-7 | Sweep step length |

#### Channel 2 (Square)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `ch2wpd` | int | 2 | 0-3 | Wave pattern duty cycle |
| `ch2vol` | int | 15 | 0-15 | Channel 2 volume |
| `ch2vsd` | bool | 0 | 0-1 | Volume sweep direction |
| `ch2ssl` | int | 0 | 0-7 | Sweep step length |

#### Channel 3 (Wave Pattern)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `ch3vol` | int | 3 | 0-3 | Channel 3 volume (0=0%, 1=100%, 2=50%, 3=25%) |
| `sampleShape` | string | - | - | Base64-encoded 32-float waveform |

#### Channel 4 (Noise)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `ch4vol` | int | 15 | 0-15 | Noise channel volume |
| `ch4vsd` | bool | 0 | 0-1 | Volume sweep direction |
| `ch4ssl` | int | 0 | 0-7 | Sweep step length |
| `srw` | bool | 0 | 0-1 | Shift register width (0=15-bit, 1=7-bit) |

#### Output Routing

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `so1vol` | int | 7 | 0-7 | Right output level |
| `so2vol` | int | 7 | 0-7 | Left output level |
| `ch1so1` | bool | 1 | 0-1 | Channel 1 to Right output |
| `ch2so1` | bool | 1 | 0-1 | Channel 2 to Right output |
| `ch3so1` | bool | 1 | 0-1 | Channel 3 to Right output |
| `ch4so1` | bool | 0 | 0-1 | Channel 4 to Right output |
| `ch1so2` | bool | 1 | 0-1 | Channel 1 to Left output |
| `ch2so2` | bool | 1 | 0-1 | Channel 2 to Left output |
| `ch3so2` | bool | 1 | 0-1 | Channel 3 to Left output |
| `ch4so2` | bool | 0 | 0-1 | Channel 4 to Left output |

#### Tone Controls

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `Treble` | float | -20 | -100 to 200 | Treble EQ |
| `Bass` | float | 461 | -1 to 600 | Bass frequency |

### Wave Pattern Storage (Channel 3)

Channel 3 uses a custom 32-sample waveform stored as Base64-encoded floats:

```cpp
// Encoding
QString sampleString;
base64::encode((const char *)m_graphModel.samples(),
    m_graphModel.length() * sizeof(float), sampleString);
_this.setAttribute("sampleShape", sampleString);

// Decoding
int size = 0;
char * dst = 0;
base64::decode(_this.attribute("sampleShape"), &dst, &size);
m_graphModel.setSamples((float*) dst);
```

- **Graph Length**: 32 samples
- **Value Range**: 0-15 (4-bit values, like the original Game Boy)
- In the Game Boy hardware, these are packed as 2 samples per byte (16 bytes total for the waveform)

### Game Boy APU Architecture

FreeBoy emulates the original Game Boy sound hardware:

| Channel | Type | Description |
|---------|------|-------------|
| 1 | Square | With frequency sweep capability |
| 2 | Square | Basic square wave |
| 3 | Wave | User-defined 32-sample waveform |
| 4 | Noise | Pseudo-random noise generator |

### Frequency Calculation

The Game Boy uses an 11-bit frequency register:

```
Frequency = 4194304 / ((2048 - (11-bit-freq)) << 5)
```

For noise channel (Channel 4):
```
PRNG Frequency = (1048576 Hz / (ratio + 1)) / 2^(shiftclockfreq + 1)
```

### Duty Cycle Values

| Value | Duty Cycle |
|-------|------------|
| 0 | 12.5% |
| 1 | 25% |
| 2 | 50% |
| 3 | 75% |

### Channel 3 Volume Encoding

The Game Boy's Channel 3 has a unique volume mapping:

| Value | Volume |
|-------|--------|
| 0 | 0% (mute) |
| 1 | 100% |
| 2 | 50% |
| 3 | 25% |

### Technical Details

- **Clock Rate**: 4,194,304 Hz (original Game Boy clock)
- **Frame Length**: 70,224 cycles
- **Sample Buffer**: 2048 samples stereo
- **Release Time**: ~23ms

### Example Complete FreeBoy Track

```xml
<track type="0" name="Chiptune Lead" muted="0" solo="0" trackheight="64">
  <instrumenttrack vol="100" pan="0" pitch="0" pitchrange="1" 
                   mixch="0" basenote="69" usemasterpitch="1">
    <instrument name="FreeBoy">
      <FreeBoy st="4" sd="0" srs="4" ch1wpd="2" ch1vol="15" ch1vsd="0" ch1ssl="0"
                ch2wpd="2" ch2vol="12" ch2vsd="0" ch2ssl="0"
                ch3vol="3"
                ch4vol="8" ch4vsd="0" ch4ssl="0" srw="0"
                so1vol="7" so2vol="7"
                ch1so1="1" ch2so1="1" ch3so1="1" ch4so1="0"
                ch1so2="1" ch2so2="1" ch3so2="1" ch4so2="0"
                Treble="-20" Bass="461"
                sampleShape="AAAAPwAAAD4AAAA/AAAAPwAAAD4AAAA/AAAAPwAAAD4AAAA/AAAAPw=="/>
    </instrument>
    <eldata fcut="14000" fres="0.5" ftype="0" fwet="0"/>
    <chordcreator chord-enabled="0"/>
    <arpeggiator arp-enabled="0"/>
    <fxchain enabled="0" numofeffects="0"/>
  </instrumenttrack>
  <midiclip pos="0" len="384" name="8-bit Melody" muted="0" type="1">
    <note pos="0" len="96" key="72" vol="100" pan="0"/>
    <note pos="96" len="96" key="74" vol="100" pan="0"/>
    <note pos="192" len="96" key="77" vol="100" pan="0"/>
    <note pos="288" len="96" key="79" vol="100" pan="0"/>
  </midiclip>
</track>
```

---

## Nescaline (NES-style Synthesizer)

Nescaline is a NES-like synthesizer that emulates the sound characteristics of the Nintendo Entertainment System's APU (Audio Processing Unit).

### Nescaline Structure

```xml
<track type="0" name="Nescaline" muted="0" solo="0">
  <instrumenttrack vol="100" pan="0" mixch="0" basenote="69">
    <instrument name="Nescaline">
      <Nescaline on1="1" crs1="0" vol1="15" envon1="0" envloop1="0" envlen1="0" dc1="0"
                 sweep1="0" swamt1="0" swrate1="0"
                 on2="1" crs2="0" vol2="15" envon2="0" envloop2="0" envlen2="0" dc2="2"
                 sweep2="0" swamt2="0" swrate2="0"
                 on3="1" crs3="0" vol3="15"
                 on4="0" vol4="15" envon4="0" envloop4="0" envlen4="0"
                 nmode4="0" nfrqmode4="0" nfreq4="0" nq4="1" nswp4="0"
                 vol="1" vibr="0"/>
    </instrument>
  </instrumenttrack>
  <midiclip pos="0" len="192" muted="0">
    <note pos="0" len="48" key="69" vol="100"/>
  </midiclip>
</track>
```

### Nescaline Attributes

#### Channel 1 (Pulse with Sweep)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `on1` | bool | 1 | 0-1 | Channel 1 enable |
| `crs1` | float | 0 | -24 to 24 | Coarse detune (semitones) |
| `vol1` | float | 15 | 0-15 | Channel 1 volume |
| `envon1` | bool | 0 | 0-1 | Envelope enable |
| `envloop1` | bool | 0 | 0-1 | Envelope loop |
| `envlen1` | float | 0 | 0-15 | Envelope length |
| `dc1` | int | 0 | 0-3 | Duty cycle (see table below) |
| `sweep1` | bool | 0 | 0-1 | Sweep enable |
| `swamt1` | float | 0 | -7 to 7 | Sweep amount |
| `swrate1` | float | 0 | 0-7 | Sweep rate |

#### Channel 2 (Pulse with Sweep)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `on2` | bool | 1 | 0-1 | Channel 2 enable |
| `crs2` | float | 0 | -24 to 24 | Coarse detune (semitones) |
| `vol2` | float | 15 | 0-15 | Channel 2 volume |
| `envon2` | bool | 0 | 0-1 | Envelope enable |
| `envloop2` | bool | 0 | 0-1 | Envelope loop |
| `envlen2` | float | 0 | 0-15 | Envelope length |
| `dc2` | int | 2 | 0-3 | Duty cycle |
| `sweep2` | bool | 0 | 0-1 | Sweep enable |
| `swamt2` | float | 0 | -7 to 7 | Sweep amount |
| `swrate2` | float | 0 | 0-7 | Sweep rate |

#### Channel 3 (Triangle)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `on3` | bool | 1 | 0-1 | Channel 3 enable |
| `crs3` | float | 0 | -24 to 24 | Coarse detune (semitones) |
| `vol3` | float | 15 | 0-15 | Channel 3 volume |

#### Channel 4 (Noise)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `on4` | bool | 0 | 0-1 | Channel 4 enable |
| `vol4` | float | 15 | 0-15 | Noise channel volume |
| `envon4` | bool | 0 | 0-1 | Envelope enable |
| `envloop4` | bool | 0 | 0-1 | Envelope loop |
| `envlen4` | float | 0 | 0-15 | Envelope length |
| `nmode4` | bool | 0 | 0-1 | Noise mode (LFSR width: 0=15-bit, 1=7-bit) |
| `nfrqmode4` | bool | 0 | 0-1 | Frequency mode (0=preset, 1=note frequency) |
| `nfreq4` | float | 0 | 0-15 | Noise frequency preset |
| `nq4` | bool | 1 | 0-1 | Quantize noise frequency to preset values |
| `nswp4` | float | 0 | -7 to 7 | Frequency sweep |

#### Master Controls

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `vol` | float | 1.0 | 0-2 | Master volume |
| `vibr` | float | 0 | 0-15 | Vibrato amount |

### Duty Cycle Values

| Value | Duty Cycle |
|-------|------------|
| 0 | 12.5% |
| 1 | 25% |
| 2 | 50% |
| 3 | 75% |

### NES APU Architecture

Nescaline emulates the four sound channels of the NES:

| Channel | Type | Description |
|---------|------|-------------|
| 1 | Pulse | Square wave with hardware sweep |
| 2 | Pulse | Square wave with hardware sweep |
| 3 | Triangle | Fixed triangle waveform |
| 4 | Noise | Pseudo-random noise via LFSR |

### Noise Frequency Presets

The noise channel uses 16 preset frequencies based on the NES hardware:

| Value | Frequency (Hz) |
|-------|----------------|
| 0 | 4069 |
| 1 | 2035 |
| 2 | 1017 |
| 3 | 763 |
| 4 | 509 |
| 5 | 381 |
| 6 | 255 |
| 7 | 193 |
| 8 | 161 |
| 9 | 129 |
| 10 | 97 |
| 11 | 65 |
| 12 | 33 |
| 13 | 17 |
| 14 | 9 |
| 15 | 5 |

The formula: `freq = 895000 / divisor`

### Envelope System

The envelope creates a decay effect:

```cpp
int envLen = wavelength(240.0 / (envLen + 1));
// Envelope decays from 15 to 0 over the specified length
```

When looped, the envelope resets to 15 and repeats.

### Sweep Implementation

Hardware sweep for pulse channels:

- Positive sweep: wavelength increases (pitch drops)
- Negative sweep: wavelength decreases (pitch rises)
- Channel 1 has an additional -1 offset on negative sweep (NES hardware quirk)

```cpp
if (sweep > 0) {
    wavelength += wavelength >> abs(sweep);
}
if (sweep < 0) {
    wavelength -= wavelength >> abs(sweep);
    // Channel 1 only: wavelength--; (additional minus 1)
}
```

### LFSR (Linear Feedback Shift Register)

The noise channel uses a 15-bit or 7-bit LFSR:

- Mode 0 (15-bit): Taps at bits 14 and 13
- Mode 1 (7-bit): Taps at bits 14 and 8

### Triangle Wavetable

Channel 3 uses a fixed 32-step triangle wavetable:

```cpp
const int TRIANGLE_WAVETABLE[32] = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
    15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0
};
```

### Vibrato

The vibrato uses the triangle wavetable for smooth pitch modulation:

- Rate: 32 samples per cycle
- Maximum depth: ~2% pitch variation at maximum setting

### Mixing and Dithering

Nescaline simulates NES analog output characteristics:

- **Dithering**: Small amount of noise added (1/60 amplitude)
- **Nonlinear Distortion**: Slight curve applied (`NES_DIST = 0.9`)
- **Low-pass Filter**: Simple first-order IIR to simulate analog rolloff
- **Hardwired Mixing**: Channels 1+2 mixed at 1/20, Channels 3+4 at 1/12

### Example Complete Nescaline Track

```xml
<track type="0" name="NES Synth" muted="0" solo="0" trackheight="64">
  <instrumenttrack vol="100" pan="0" pitch="0" pitchrange="1" 
                   mixch="0" basenote="69" usemasterpitch="1">
    <instrument name="Nescaline">
      <Nescaline on1="1" crs1="0" vol1="12" envon1="1" envloop1="0" envlen1="7" dc1="1"
                 sweep1="1" swamt1="3" swrate1="4"
                 on2="1" crs2="12" vol2="10" envon2="0" envloop2="0" envlen2="0" dc2="2"
                 sweep2="0" swamt2="0" swrate2="0"
                 on3="1" crs3="0" vol3="15"
                 on4="1" vol4="8" envon4="1" envloop4="0" envlen4="5"
                 nmode4="0" nfrqmode4="0" nfreq4="8" nq4="1" nswp4="3"
                 vol="1" vibr="3"/>
    </instrument>
    <eldata fcut="14000" fres="0.5" ftype="0" fwet="0"/>
    <chordcreator chord-enabled="0"/>
    <arpeggiator arp-enabled="0"/>
    <fxchain enabled="0" numofeffects="0"/>
  </instrumenttrack>
  <midiclip pos="0" len="384" name="NES Melody" muted="0" type="1">
    <note pos="0" len="96" key="60" vol="100" pan="0"/>
    <note pos="96" len="96" key="64" vol="100" pan="0"/>
    <note pos="192" len="96" key="67" vol="100" pan="0"/>
    <note pos="288" len="96" key="72" vol="100" pan="0"/>
  </midiclip>
</track>
```

### Technical Details

- **Base Clock**: 895,000 Hz (for noise frequency calculations)
- **Minimum Wavelength**: 4 samples
- **Release Time**: ~0.2ms
- **DC Offset Compensation**: Applied after nonlinear distortion


---

## TripleOscillator

TripleOscillator is LMMS's flagship synthesizer instrument featuring three powerful oscillators with multiple modulation options.

### TripleOscillator Structure

```xml
<track type="0" name="TripleOscillator" muted="0" solo="0">
  <instrumenttrack vol="100" pan="0" mixch="0" basenote="69">
    <instrument name="TripleOscillator">
      <TripleOscillator 
          vol0="33" pan0="0" coarse0="0" finel0="0" finer0="0" 
          phoffset0="0" stphdetun0="0" wavetype0="0" modalgo1="2" 
          useWaveTable1="1" userwavefile0=""
          vol1="33" pan1="0" coarse1="-12" finel1="0" finer1="0"
          phoffset1="0" stphdetun1="0" wavetype1="0" modalgo2="2"
          useWaveTable2="1" userwavefile1=""
          vol2="33" pan2="0" coarse2="-24" finel2="0" finer2="0"
          phoffset2="0" stphdetun2="0" wavetype2="0"
          useWaveTable3="1" userwavefile2=""/>
    </instrument>
  </instrumenttrack>
  <midiclip pos="0" len="192" muted="0">
    <note pos="0" len="48" key="69" vol="100"/>
  </midiclip>
</track>
```

### Oscillator Attributes (per oscillator 0-2)

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `volN` | float | 33.33 | 0-200 | Volume percentage (N=0,1,2) |
| `panN` | float | 0 | -100 to 100 | Panning (N=0,1,2) |
| `coarseN` | int | 0,-12,-24 | -24 to 24 | Coarse detune (semitones) |
| `finelN` | float | 0 | -100 to 100 | Fine detune left (cents) |
| `finerN` | float | 0 | -100 to 100 | Fine detune right (cents) |
| `phoffsetN` | float | 0 | 0-360 | Phase offset (degrees) |
| `stphdetunN` | float | 0 | 0-360 | Stereo phase detuning (degrees) |
| `wavetypeN` | int | 0 | 0-7 | Wave shape (see table below) |
| `userwavefileN` | string | - | - | Path to user waveform file |
| `useWaveTableN` | bool | 1 | 0-1 | Use anti-aliased wavetable |

### Modulation Algorithm Attributes

| Attribute | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `modalgo1` | int | 2 | 0-4 | Modulation between Osc1 and Osc2 |
| `modalgo2` | int | 2 | 0-4 | Modulation between Osc2 and Osc3 |

### Wave Shapes

| Value | Wave Shape | Description |
|-------|------------|-------------|
| 0 | Sine | Pure sine wave |
| 1 | Triangle | Triangle wave |
| 2 | Saw | Sawtooth wave |
| 3 | Square | Square wave |
| 4 | Moog Saw | Moog-style sawtooth |
| 5 | Exponential | Exponential curve |
| 6 | White Noise | White noise |
| 7 | User | User-defined waveform from file |

### Modulation Algorithms

| Value | Algorithm | Description |
|-------|-----------|-------------|
| 0 | PM | Phase modulation (osc1 phase modulated by osc2) |
| 1 | AM | Amplitude modulation (osc1 amplitude modulated by osc2) |
| 2 | Mix | Signal mix (simple additive mixing) |
| 3 | Sync | Sync (osc1 synced to osc2 frequency) |
| 4 | FM | Frequency modulation (osc1 frequency modulated by osc2) |

### Signal Flow

The oscillators are processed in reverse order for modulation:

```
Osc2 → modulates → Osc1
Osc3 → modulates → Osc2
```

Each oscillator pair can use different modulation algorithms, creating complex timbres.

### Detuning Calculation

Detuning is calculated using the formula:

```cpp
detuning = exp2((coarse * 100.0 + fine) / 1200.0) / sampleRate;
```

This converts semitones and cents to a frequency multiplier.

### Phase Offset System

Each oscillator has two phase controls:

- **Phase Offset**: Base phase offset (0-360°)
- **Stereo Phase Detuning**: Additional offset added to left channel only

Left channel phase: `(phaseOffset + stereoPhaseDetuning) / 360`
Right channel phase: `phaseOffset / 360`

This creates stereo width through phase differences.

### Wavetable Mode

When `useWaveTableN="1"`:
- Uses anti-aliased wavetable oscillators
- Reduces aliasing artifacts at high frequencies
- Generated via `Oscillator::generateAntiAliasUserWaveTable()` for user waves

### Default Values

Default coarse detuning is staggered for rich sound:
- Oscillator 0: 0 semitones
- Oscillator 1: -12 semitones (one octave down)
- Oscillator 2: -24 semitones (two octaves down)

Default volume is split equally: 100/3 ≈ 33.33% per oscillator

### Example Complete TripleOscillator Track

```xml
<track type="0" name="Synth Lead" muted="0" solo="0" trackheight="64">
  <instrumenttrack vol="100" pan="0" pitch="0" pitchrange="2" 
                   mixch="0" basenote="69" usemasterpitch="1">
    <instrument name="TripleOscillator">
      <TripleOscillator 
          vol0="40" pan0="0" coarse0="0" finel0="5" finer0="-5" 
          phoffset0="0" stphdetun0="0" wavetype0="2" modalgo1="4" 
          useWaveTable1="1" userwavefile0=""
          vol1="35" pan1="0" coarse1="-12" finel1="0" finer1="0"
          phoffset1="0" stphdetun1="0" wavetype1="2" modalgo2="2"
          useWaveTable2="1" userwavefile1=""
          vol2="25" pan2="0" coarse2="-24" finel2="0" finer2="0"
          phoffset2="180" stphdetun2="0" wavetype2="3"
          useWaveTable3="1" userwavefile2=""/>
    </instrument>
    <eldata fcut="14000" fres="0.5" ftype="0" fwet="0"/>
    <chordcreator chord-enabled="0"/>
    <arpeggiator arp-enabled="0"/>
    <fxchain enabled="0" numofeffects="0"/>
  </instrumenttrack>
  <midiclip pos="0" len="384" name="Lead Line" muted="0" type="1">
    <note pos="0" len="96" key="60" vol="100" pan="0"/>
    <note pos="96" len="96" key="64" vol="100" pan="0"/>
    <note pos="192" len="96" key="67" vol="100" pan="0"/>
    <note pos="288" len="96" key="72" vol="100" pan="0"/>
  </midiclip>
</track>
```

### Technical Details

- **Number of Oscillators**: 3 (constant `NUM_OF_OSCILLATORS`)
- **Release Time**: ~3ms
- **Sample Rate Independence**: All detuning calculations normalized to sample rate


---

## Volume and Gain Signal Flow

LMMS has a hierarchical volume/gain system where multiple volume controls affect the final output. Understanding this signal flow is essential for properly interpreting saved project values.

### Signal Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INSTRUMENT TRACK                                   │
│  ┌──────────┐    ┌───────────────────┐    ┌────────────────┐               │
│  │   Note   │    │  Instrument Track │    │  AudioBusHandle │               │
│  │  Volume  │ -> │    Volume/Pan     │ -> │    Effects      │               │
│  │ (0-200)  │    │    (0-200/-100-100)│    │   (FX Chain)    │               │
│  └──────────┘    └───────────────────┘    └────────────────┘               │
│                          │                          │                        │
│                          │ mixch (channel assign)   │                        │
│                          ▼                          ▼                        │
└─────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MIXER                                           │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐            │
│  │ Mixer Channel  │    │ Mixer Channel  │    │ Master Channel │            │
│  │     (FX 1)     │ -> │     (FX N)     │ -> │    (Channel 0) │            │
│  │ volume (0-2)   │    │ volume (0-2)   │    │  volume (0-2)  │            │
│  └────────────────┘    └────────────────┘    └────────────────┘            │
│         │                     │                      │                      │
│         │ send amount (0-1)   │ send amount (0-1)    │                      │
│         └─────────────────────┴──────────────────────┘                      │
│                                      │                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MASTER OUTPUT                                      │
│                    ┌────────────────────────┐                               │
│                    │  Master Volume (0-200) │                               │
│                    │   (from <head>)        │                               │
│                    └────────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Volume Controls in Detail

#### 1. Note Volume (`<note vol="...">`)

| Property | Value |
|----------|-------|
| **Attribute** | `vol` |
| **Range** | 0-200 |
| **Default** | 100 |
| **Storage** | Per-note in MIDI clips |

Note velocity is scaled by this value. A note with `vol="50"` plays at half volume, `vol="200"` at double volume.

**Conversion from MIDI velocity:**
```cpp
// MIDI velocity (0-127) to LMMS volume
volume = velocity * DefaultVolume / midiBaseVelocity;
// where midiBaseVelocity = 64
```

**Conversion to MIDI velocity:**
```cpp
velocity = min(127, volume * 64 / 100);
```

#### 2. Instrument Track Volume (`<instrumenttrack vol="...">`)

| Property | Value |
|----------|-------|
| **Attribute** | `vol` |
| **Range** | 0-200 |
| **Default** | 100 |
| **Storage** | Instrument track element |

Applied in `AudioBusHandle::doProcessing()`:

```cpp
float v = m_volumeModel->value() * 0.01f;  // Convert to linear (0-2)
buffer[f][0] *= v;
buffer[f][1] *= v;
```

#### 3. Instrument Track Panning (`<instrumenttrack pan="...">`)

| Property | Value |
|----------|-------|
| **Attribute** | `pan` |
| **Range** | -100 (left) to 100 (right) |
| **Default** | 0 (center) |
| **Storage** | Instrument track element |

Applied as constant power panning:

```cpp
float p = m_panningModel->value() * 0.01f;  // -1.0 to 1.0
// Left channel: boost when panned right, cut when panned left
buffer[f][0] *= (p <= 0 ? 1.0f : 1.0f - p) * v;
// Right channel: boost when panned left, cut when panned right
buffer[f][1] *= (p >= 0 ? 1.0f : 1.0f + p) * v;
```

| Panning Value | Left Gain | Right Gain |
|---------------|-----------|------------|
| -100 (full left) | 1.0 | 0.0 |
| -50 | 1.0 | 0.5 |
| 0 (center) | 1.0 | 1.0 |
| 50 | 0.5 | 1.0 |
| 100 (full right) | 0.0 | 1.0 |

#### 4. Mixer Channel Assignment (`<instrumenttrack mixch="...">`)

| Property | Value |
|----------|-------|
| **Attribute** | `mixch` |
| **Range** | 0+ (0 = Master) |
| **Default** | 0 |
| **Storage** | Instrument track element |

Determines which mixer channel receives the instrument's output after its volume/panning and effect chain.

#### 5. Mixer Channel Volume (`<mixerchannel volume="...">`)

| Property | Value |
|----------|-------|
| **Attribute** | `volume` |
| **Range** | 0.0-2.0 (0%-200%) |
| **Default** | 1.0 (100%) |
| **Storage** | Mixer channel element |

This is a **linear fader**, not a percentage like track volume:

```cpp
m_volumeModel(1.f, 0.f, 2.f, 0.001f, _parent)
```

Applied when mixing channel sends:

```cpp
const float v = sender->m_volumeModel.value() * sendModel->value();
MixHelpers::addSanitizedMultiplied(buffer.data(), ch_buf.data(), v, fpp);
```

#### 6. Mixer Channel Sends (`<send amount="...">`)

| Property | Value |
|----------|-------|
| **Attribute** | `amount` |
| **Range** | 0.0-1.0 |
| **Default** | 1.0 (for default send to master) |
| **Storage** | Child of mixerchannel element |

```xml
<mixerchannel num="1" name="FX 1">
  <send channel="0" amount="0.8"/>  <!-- 80% send to master -->
</mixerchannel>
```

#### 7. Master Volume (`<head mastervol="...">`)

| Property | Value |
|----------|-------|
| **Attribute** | `mastervol` |
| **Range** | 0-200 |
| **Default** | 100 |
| **Storage** | Head element |

Applied to the final output in `Mixer::masterMix()`:

```cpp
const float v = m_mixerChannels[0]->m_volumeModel.value();
MixHelpers::addSanitizedMultiplied(_buf, buffer.data(), v, fpp);
```

Note: The mixer master channel volume (0-2) is separate from the head mastervol (0-200). The master channel is channel 0 in the mixer.

### Complete Gain Calculation Example

For an instrument track with no effects, the final output gain is:

```
FinalGain = NoteVolume/100 × TrackVolume/100 × PanGain × MixerChannelVolume × SendAmount × MasterVolume/100
```

**Example Calculation:**

Given:
- Note: `vol="80"`
- Instrument Track: `vol="75"`, `pan="50"` (panned right)
- Mixer Channel: `volume="0.9"` (channel 1)
- Send to Master: `amount="0.5"`
- Master Volume: `mastervol="100"`

For the **right channel**:
```
NoteGain = 80/100 = 0.8
TrackGain = 75/100 = 0.75
PanGain = 1.0 (panned right, right channel at full)
MixerGain = 0.9
SendGain = 0.5
MasterGain = 100/100 = 1.0

FinalRightGain = 0.8 × 0.75 × 1.0 × 0.9 × 0.5 × 1.0 = 0.27
```

For the **left channel**:
```
PanGain = 1.0 - 0.5 = 0.5 (panned right, left channel reduced)

FinalLeftGain = 0.8 × 0.75 × 0.5 × 0.9 × 0.5 × 1.0 = 0.135
```

### Volume Constants Reference

```cpp
// From volume.h
constexpr volume_t MinVolume = 0;
constexpr volume_t MaxVolume = 200;
constexpr volume_t DefaultVolume = 100;
```

### Volume Value Interpretation

| Context | Attribute | Range | Scaling |
|---------|-----------|-------|---------|
| Note | `vol` | 0-200 | `/100` for linear multiplier |
| Instrument Track | `vol` | 0-200 | `/100` for linear multiplier |
| Instrument Track | `pan` | -100 to 100 | `/100` for panning factor |
| Sample Track | `vol` | 0-200 | `/100` for linear multiplier |
| Sample Track | `pan` | -100 to 100 | `/100` for panning factor |
| Mixer Channel | `volume` | 0-2 | Direct linear multiplier |
| Mixer Send | `amount` | 0-1 | Direct linear multiplier |
| Master (head) | `mastervol` | 0-200 | `/100` for linear multiplier |

### Sample-Exact Volume (Automation)

When volume is automated, LMMS uses sample-exact processing via `ValueBuffer`:

```cpp
ValueBuffer* volBuf = m_volumeModel->valueBuffer();
if (volBuf) {
    // Sample-exact: each sample frame has its own volume value
    for (f_cnt_t f = 0; f < fpp; ++f) {
        buffer[f][0] *= volBuf->values()[f] * 0.01f;
        buffer[f][1] *= volBuf->values()[f] * 0.01f;
    }
}
```

This ensures smooth volume transitions without zipper noise.

### Mute and Solo

**Mute** sets volume to 0:

```xml
<instrumenttrack muted="1"/>  <!-- muted track -->
<mixerchannel muted="1"/>      <!-- muted channel -->
```

**Solo** mutes all other channels except the soloed one and its routing chain:

```xml
<mixerchannel soloed="1"/>     <!-- soloed channel -->
```

The solo system tracks `mutedBeforeSolo` to restore previous states:

```xml
<track muted="0" solo="1" mutedBeforeSolo="0"/>
```

---

## References

- Source code: `lmms/src/core/DataFile.cpp`
- Header: `lmms/include/DataFile.h`
- Track system: `lmms/src/core/Track.cpp`
- Song model: `lmms/src/core/Song.cpp`
- MIDI clips: `lmms/src/tracks/MidiClip.cpp`
- Automation: `lmms/src/tracks/AutomationClip.cpp`
- Sample Track: `lmms/src/tracks/SampleTrack.cpp`
- Sample Clip: `lmms/src/core/SampleClip.cpp`
- Sample: `lmms/include/Sample.h`
- Sample Buffer: `lmms/src/core/SampleBuffer.cpp`
- VeSTige: `lmms/plugins/vestige/Vestige.cpp`
- VST Plugin base: `lmms/plugins/VstBase/VstPlugin.cpp`
