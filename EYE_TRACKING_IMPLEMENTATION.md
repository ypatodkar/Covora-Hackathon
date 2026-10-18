# FocalPoint Eye Tracking Implementation Details

This document details the architecture, functionality, and specific implementation mechanisms behind the gaze-driven tracking engine built for FocalPoint.

## 1. Overview
FocalPoint utilizes **WebGazer.js** (powered by MediaPipe's Face Mesh) to perform real-time, webcam-based eye tracking directly in the browser. 

The primary goal of the system is to **deeply understand what the user is looking at and for how long**, down to the precise word. This telemetry can be used to gauge cognitive load, reading speed, and areas of confusion to dynamically adapt the complexity of the response.

## 2. Word-Level Precision Mapping
Instead of mapping eye coordinates to large block elements (like entire paragraphs), the system achieves pinpoint accuracy by structurally altering how text is rendered.

**How it works:**
1. **DOM Injection**: When the AI assistant generates a response (e.g., the "wall of text"), `ResponseDisplay.jsx` intercepts the text string and splits it by spaces.
2. **Span Wrapping**: Every individual word is wrapped in its own `<span class="gaze-word" data-word-id="zone_0_wX">` tag. 
3. **Intersection**: The raw `(X, Y)` gaze coordinates are passed to `gazeUtils.js`, which uses the native browser API `document.elementFromPoint(x, y)` to find the topmost DOM element at that exact pixel. If the element is a `.gaze-word`, we instantly know precisely which word the user's fovea is fixated on.

## 3. Dynamic EMA Smoothing (Jitter Elimination)
Raw webcam eye-tracking data is inherently noisy, causing the cursor to "jitter" even when the user's eye is perfectly still. Applying a standard smoothing filter reduces jitter but introduces significant lag when the user moves their eyes quickly (a saccade).

**How it works:**
We implemented a **Dynamic Exponential Moving Average (EMA)** algorithm in `App.jsx` that adjusts its smoothing factor (`alpha`) in real-time based on the distance of the eye movement.

- **Micro-Jitters (Distance < 20px)**: The system assumes the user is fixated on a single word and the movement is just webcam noise. It applies an ultra-low alpha (`0.02`), creating massive "stickiness". The cursor anchors solidly to the word.
- **Transitions (Distance < 50px)**: A moderate alpha (`0.1`) is applied for slow scanning.
- **Saccades (Distance > 50px)**: The system assumes the user is jumping to a new line or paragraph. It applies a high alpha (`0.4`), snapping the cursor instantly to the new location without dragging or lagging behind.

## 4. Reading Duration Telemetry
Understanding *how long* a user looks at a word is critical for inferring confusion or cognitive load.

**How it works:**
1. Inside `handleGazeUpdate`, React `useRef` hooks maintain the `currentReadingLine` (the current word ID) and the `startTime` (when the gaze first hit this word).
2. As the user reads, the tracker continually compares the current word to the stored word.
3. When the gaze shifts to a *new* word, the system calculates `currentTime - startTime`.
4. It logs the exact string of the word that was just completed, along with the fixation duration in milliseconds, directly to the output stream (and browser console). It then resets the timer for the new word.

## 5. UI & Debugging
- **Webcam Feed**: The WebGazer video feed and face mesh visualization are positioned fixed in the bottom-right corner of the interface (`WebGazerController.jsx`), allowing the user to verify the tracker is capturing their eyes.
- **Live Gaze Stream**: A continuous, auto-scrolling telemetry log is appended to the DOM in the right-side stats panel. This stream outputs timestamps, smoothed X/Y coordinates, and the active word ID at 60 FPS, providing a transparent view of the engine's raw data feed.
