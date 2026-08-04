# CP3 1.5.27 Protocol Findings

## Confirmed device transport

The CP3 USB device exposes only a standard CDC ACM function:

- Interface 0: CDC control
- Interface 1: CDC data
- Bulk IN endpoint `0x81`
- Bulk OUT endpoint `0x01`
- Interrupt IN endpoint `0x82`

There is no separate vendor-specific USB interface. The official application contains the Node `@serialport` packages and scans/open serial ports.

## Application packaging

The Windows application is an Electron application. Its `app.asar` contains:

- `out/main/index.jsc` — compiled Electron main-process bytecode
- `out/preload/index.jsc` — compiled preload bytecode
- Renderer JavaScript bundles
- `@serialport`
- `ffi-napi`
- `node-hid`
- `fluent-ffmpeg`

The main application logic is compiled as V8 bytecode (`.jsc`), but meaningful string constants are still recoverable.

## Protocol framing recovered from main-process bytecode

The bytecode contains a request/response protocol with these headers:

- `SeqNumber`
- `AckNumber`
- `ContentLength`
- `ContentType`
- `FileName`
- `FileBlockId`
- `FileSize`
- `ContentRange`
- `Counter`
- `Option`

It also contains protocol concepts and methods including:

- `packData`
- `unpackMsg`
- `getMessagePacket`
- `getMessageLength`
- `getMessageBuffer`
- `Response Message`
- `Protocol version not match`
- `data frame is incomplete`
- request sequence queues and response callbacks

This matches the text-based request/response envelope already observed by the Linux implementation, but confirms the official application has additional file-transfer operations.

## Media pipeline recovered

The official application exposes these IPC operations:

- `waterBlockScreen:mediaList`
- `waterBlockScreen:mediaSave`
- `waterBlockScreen:mediaFrameGet`
- `waterBlockScreen:mediaInfoGet`
- `waterBlockScreen:mediaImageAdd`
- `waterBlockScreen:mediaImageGifAdd`
- `waterBlockScreen:mediaVideoAdd`
- `waterBlockScreen:mediaVideoCropAdd`
- `waterBlockScreen:mediaConvert`
- `waterBlockScreen:mediaDelete`

Renderer code calls these methods directly. Static images are cropped to a PNG buffer and passed to `mediaImageAdd`. GIF and video use dedicated media paths rather than the static-image frame path.

## Video/GIF preparation

The main process uses FFmpeg and `MediaStation.dll`.

Recovered FFmpeg options include:

- `-pix_fmt yuv420p`
- `-bf 0`
- `-movflags faststart`
- even-dimension crop and scale filters
- GIF-to-video conversion

Recovered native DLL entry points include:

- `VideoClip`
- `ImageClip`
- `StopClip`
- `CatchVideoFrame`
- `CatchGifFrame`
- `GetVideoInfo`
- `GetGifInfo`

The application logs `mediaVideoAdd session` and `mediaImageGifAdd` operations, indicating it prepares a media file and then passes it into a dedicated upload transaction.

## Most likely explanation for smooth playback

The official application does not appear to repeatedly send independent PNG frames for GIF or MP4 playback. It has dedicated GIF/video add operations, converts GIF to MP4 when needed, prepares media with FFmpeg/MediaStation, and transfers the resulting media as a file.

The likely flow is:

1. Crop/scale/transcode media to a CP3-compatible MP4.
2. Start a file-transfer session.
3. Send the file using block headers (`FileBlockId`, `FileSize`, `ContentRange`).
4. Mark the media as stored/available.
5. Select the stored media as the screen background.
6. The CP3 firmware plays the media locally.

This explains why full-frame PNG streaming is limited to about 2 FPS while the official application displays smooth animation.

## Next implementation target

Beta 11 should add an experimental native-media uploader using the existing CDC serial transport:

- `media-list`
- `media-info`
- `media-upload`
- `media-delete`
- `media-select`

The first practical goal is to capture or reconstruct the request command names and exact body format for `mediaVideoAdd` and the file block transfer. The recovered header names are sufficient to build a protocol tracer around the existing connection class.
