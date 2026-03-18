# LMMS CLI Specification

## Overview

LMMS (Linux Multimedia Studio) is a free cross-platform digital audio workstation. This document specifies the command-line interface (CLI) for LMMS, detailing all available actions, options, and parameters.

## Synopsis

```
lmms [global options...] [<action> [action parameters...]]
```

---

## Global Options

These options can be used with any action or when starting LMMS in GUI mode.

| Option | Description |
|--------|-------------|
| `--allowroot` | Bypass root user startup check (use with caution). On Linux/Unix systems, LMMS refuses to run as root by default. This flag overrides that safety check. |
| `-c, --config <configfile>` | Use the specified configuration file instead of the default (`~/.lmmsrc.xml` on Linux/Mac, or the appropriate user config location on Windows). |
| `-h, --help` | Display usage information and exit. |
| `-v, --version` | Display version information and exit. |

---

## Actions

### 1. No Action (Default GUI Mode)

**Usage:**
```
lmms [global options...] [options...] [<project>]
```

**Description:**
Starts LMMS in normal GUI mode. If a project file is specified, it will be loaded on startup.

**Options:**

| Option | Description |
|--------|-------------|
| `--geometry <geometry>` | Specify the size and position of the main window. Format: `<xsizexysize+xoffset+yoffsety>` (e.g., `1024x768+100+50`). Default: full screen. |
| `--import <in> [-e]` | Import a MIDI or Hydrogen file (`*.mid`, `*.midi`, `*.rmi`, `*.h2song`). If `-e` is specified, LMMS exits after importing the file. |

**Behavior:**
- If no project file is specified and "open last project" is enabled in settings, LMMS will attempt to open the most recently used project.
- If a recovery file exists (from a previous crash), the user will be prompted to recover or discard it.
- Auto-save functionality is activated if enabled in settings.

---

### 2. dump

**Usage:**
```
lmms dump <in>
```

**Description:**
Decompresses and dumps the XML content of a compressed LMMS project file (`.mmpz`) to standard output.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `<in>` | Path to a compressed LMMS project file (`.mmpz`). |

**Output:**
Prints the uncompressed XML content to stdout.

**Exit Codes:**
- `0` - Success
- Non-zero - File not found or invalid file

---

### 3. compress

**Usage:**
```
lmms compress <in>
```

**Description:**
Compresses a file using Qt's compression algorithm and outputs the compressed data to standard output.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `<in>` | Path to the file to compress. |

**Output:**
Binary compressed data written to stdout.

---

### 4. render

**Usage:**
```
lmms render <project> [options...]
```

**Description:**
Renders a project file to an audio file (non-interactive, headless mode). This action runs without the GUI.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `<project>` | Path to the LMMS project file (`.mmp` or `.mmpz`). |

**Options:**

| Option | Description |
|--------|-------------|
| `-a, --float` | Use 32-bit float bit depth (default: 16-bit). |
| `-b, --bitrate <bitrate>` | Specify output bitrate in KBit/s. Range: 64-384. Default: 160. Primarily used for OGG/MP3 encoding. |
| `-f, --format <format>` | Specify output format. Options: `wav`, `flac`, `ogg`, `mp3`. Default: `wav`. Note: OGG requires LMMS compiled with OGG Vorbis support; MP3 requires LAME support. |
| `-i, --interpolation <method>` | Specify interpolation method. Options: `linear`, `sincfastest` (default), `sincmedium`, `sincbest`. |
| `-l, --loop` | Render as a loop, stopping exactly at the end of the song. Silence and reverb tails at the end are not rendered. |
| `-m, --mode <stereomode>` | Set stereo mode for MP3 export. Options: `s` (stereo), `j` (joint stereo, default), `m` (mono). |
| `-o, --output <path>` | Output file path. If not specified, the output file will be placed in the same location as the input project with the appropriate extension. |
| `-p, --profile <out>` | Dump profiling information to the specified file. |
| `-s, --samplerate <samplerate>` | Output sample rate in Hz. Range: 44100-192000. Default: 44100. |
| `-x, --oversampling <value>` | Specify oversampling. Options: 1, 2 (default), 4, 8. |

**Output Format Details:**

| Format | Extension | Bitrate Support | Notes |
|--------|-----------|-----------------|-------|
| WAV | `.wav` | N/A (lossless) | Default format. Supports 16/32-bit depth. |
| FLAC | `.flac` | N/A (lossless) | Lossless compressed format. |
| OGG | `.ogg` | 64-384 KBit/s | Requires OGG Vorbis support. |
| MP3 | `.mp3` | 64-384 KBit/s | Requires LAME support. |

**Progress Display:**
During rendering, progress is displayed in the console as:
```
|-----------------------|    50%   /
```
A rotating activity indicator shows rendering is in progress.

---

### 5. rendertracks

**Usage:**
```
lmms rendertracks <project> [options...]
```

**Description:**
Renders each track (instrument and sample tracks) to separate audio files. Automation tracks are not rendered individually.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `<project>` | Path to the LMMS project file (`.mmp` or `.mmpz`). |

**Options:**
Same options as `render` action (see above).

**Key Differences from `render`:**
- The `-o, --output` option specifies a directory path (must exist) rather than a file path.
- Each unmuted instrument and sample track is rendered to a separate file.
- Files are named with a numeric prefix: `<tracknum>_<trackname>.<extension>`
- Invalid characters in track names are removed.

**Example Output:**
```
/output/
├── 1_Piano.wav
├── 2_Drums.wav
├── 3_Bass.wav
└── 4_Synth.wav
```

---

### 6. upgrade

**Usage:**
```
lmms upgrade <in> [out]
```

**Description:**
Upgrades an LMMS project file to the current version format. Useful for migrating projects from older LMMS versions.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `<in>` | Path to the input LMMS project file (`.mmp` or `.mmpz`). |
| `[out]` | (Optional) Path to the output file. If omitted, the upgraded XML is written to standard output. |

**Upgrade Process:**
The upgrade process applies various transformations to ensure compatibility:
- Updates deprecated elements and attributes
- Renames changed components
- Fixes known issues from older versions
- Updates automation nodes
- Extended note range updates
- Mixer and pattern clip renaming
- Various other version-specific fixes

---

### 7. makebundle

**Usage:**
```
lmms makebundle <in> [out]
```

**Description:**
Creates a project bundle from a project file. A bundle includes the project file along with all referenced resources (samples, presets, etc.) in a single package.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `<in>` | Path to the input LMMS project file. |
| `[out]` | Path to the output bundle file. |

**Error Handling:**
- Returns an error if no output file is specified.

---

## Output Settings

### Bit Depth

| Value | Description |
|-------|-------------|
| 16-bit | Default bit depth. Standard CD quality. |
| 24-bit | Higher quality, larger files. |
| 32-bit float | Maximum quality, largest files. Enabled with `-a, --float`. |

### Sample Rate

| Value | Description |
|-------|-------------|
| 44100 | CD quality (default). |
| 48000 | Professional audio standard. |
| 96000 | High-resolution audio. |
| 192000 | Maximum supported sample rate. |

### Stereo Mode (MP3)

| Value | Description |
|-------|-------------|
| `s` | Stereo - Independent left and right channels. |
| `j` | Joint Stereo (default) - More efficient encoding. |
| `m` | Mono - Single channel. |

### Interpolation Methods

| Method | Quality | Performance |
|--------|---------|-------------|
| `linear` | Basic | Fastest |
| `sincfastest` | Good (default) | Fast |
| `sincmedium` | Better | Medium |
| `sincbest` | Best | Slowest |

---

## Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success. |
| `1` | General failure (file not found, invalid options, etc.). |
| `SIGINT` | User interrupted (Ctrl+C). |

---

## Error Handling

### Common Errors

1. **"The file does not have any content"**
   - The specified file is empty.

2. **"is a directory"**
   - A directory path was provided where a file was expected.

3. **"No input file specified"**
   - An action requiring an input file was invoked without one.

4. **"Invalid option"**
   - An unrecognized command-line option was provided.

5. **"Invalid samplerate/bitrate/format/stereo mode"**
   - An invalid value was provided for the respective option.

6. **"The project is empty, aborting!"**
   - The project file contains no content to render.

---

## File Types

### Input Files

| Extension | Description |
|-----------|-------------|
| `.mmp` | Uncompressed LMMS project file (XML). |
| `.mmpz` | Compressed LMMS project file. |
| `.mid`, `.midi`, `.MID`, `.MIDI`, `.rmi`, `.RMI` | MIDI files (import only). |
| `.h2song`, `.H2SONG` | Hydrogen song files (import only). |

### Output Files

| Extension | Description |
|-----------|-------------|
| `.wav` | Waveform Audio File Format. |
| `.flac` | Free Lossless Audio Codec. |
| `.ogg` | OGG Vorbis compressed audio. |
| `.mp3` | MP3 compressed audio. |

---

## Configuration

### Configuration File

LMMS uses an XML configuration file (default: `~/.lmmsrc.xml` on Linux/Mac). This can be overridden with the `-c, --config` option.

### Relevant Settings

| Setting | Location | Description |
|---------|----------|-------------|
| `app/language` | `[app]` section | UI language code (e.g., "en", "de"). |
| `app/openlastproject` | `[app]` section | Whether to open the last project on startup (0 or 1). |
| `app/nanhandler` | `[app]` section | Enable/disable NaN handler (0 or 1). |
| `ui/enableautosave` | `[ui]` section | Enable auto-save functionality (0 or 1). |

---

## Examples

### Starting LMMS with a Project
```bash
lmms myproject.mmpz
```

### Importing a MIDI File
```bash
lmms --import mysong.mid
```

### Import and Exit
```bash
lmms --import mysong.mid -e
```

### Render to WAV
```bash
lmms render myproject.mmpz -o output.wav
```

### Render to MP3 with Custom Settings
```bash
lmms render myproject.mmpz -f mp3 -b 320 -s 48000 -o output.mp3
```

### Render as Loop
```bash
lmms render myproject.mmpz -l -o loop.wav
```

### Render Tracks Individually
```bash
lmms rendertracks myproject.mmpz -o ./tracks/
```

### Dump Compressed Project XML
```bash
lmms dump myproject.mmpz > myproject.xml
```

### Upgrade a Project File
```bash
lmms upgrade oldproject.mmpz newproject.mmpz
```

### Create a Project Bundle
```bash
lmms makebundle myproject.mmpz mybundle.lmmsbundle
```

### Use Custom Configuration
```bash
lmms -c /path/to/custom_config.xml myproject.mmpz
```

### Render with Profiling
```bash
lmms render myproject.mmpz -p profile.log
```

---

## Platform-Specific Notes

### Windows
- Console output is handled through `AttachConsole` for proper output display.
- The `--allowroot` option is ignored (not applicable).

### Linux/Unix
- LMMS refuses to run as root unless `--allowroot` is specified.
- Signal handlers are installed for SIGINT and SIGPIPE.
- The process sets the `PR_SET_CHILD_SUBREAPER` flag to handle plugin child processes.

### macOS
- Supports file open events via Qt event handling.

---

## Signal Handling

| Signal | Behavior |
|--------|----------|
| `SIGINT` (Ctrl+C) | Clean shutdown of LMMS. |
| `SIGPIPE` | Ignored to prevent crashes when piping output. |
| `SIGFPE` | Only handled when compiled with `LMMS_DEBUG_FPE` for debugging floating-point exceptions. |

---

## See Also

- LMMS Website: https://lmms.io/
- LMMS Documentation: https://lmms.io/documentation/
- GitHub Repository: https://github.com/LMMS/lmms