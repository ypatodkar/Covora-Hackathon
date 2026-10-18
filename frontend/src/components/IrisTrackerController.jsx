import React, { useEffect, useRef, useState } from 'react';
import { Camera, CameraOff, Play, RefreshCw } from 'lucide-react';

// Built dynamically from the chat area bounds at calibration start — see buildCalibrationPoints()
const FALLBACK_CALIBRATION_POINTS = [
  { id: 1, top: 10, left: 20 }, { id: 2, top: 10, left: 50 }, { id: 3, top: 10, left: 80 },
  { id: 4, top: 35, left: 28 }, { id: 5, top: 35, left: 72 },
  { id: 6, top: 50, left: 20 }, { id: 7, top: 50, left: 50 }, { id: 8, top: 50, left: 80 },
  { id: 9, top: 65, left: 28 }, { id: 10, top: 65, left: 72 },
  { id: 11, top: 88, left: 20 }, { id: 12, top: 88, left: 50 }, { id: 13, top: 88, left: 80 },
];

function buildCalibrationPoints() {
  // Full-screen grid so the model gets a good fit across the entire eye movement range.
  // X is ignored at prediction time — only Y is used for zone lookup.
  return [
    { id: 1,  top:  5, left:  5 }, { id: 2,  top:  5, left: 50 }, { id: 3,  top:  5, left: 95 },
    { id: 4,  top: 25, left: 20 }, { id: 5,  top: 25, left: 80 },
    { id: 6,  top: 50, left:  5 }, { id: 7,  top: 50, left: 50 }, { id: 8,  top: 50, left: 95 },
    { id: 9,  top: 75, left: 20 }, { id: 10, top: 75, left: 80 },
    { id: 11, top: 95, left:  5 }, { id: 12, top: 95, left: 50 }, { id: 13, top: 95, left: 95 },
  ];
}

const CLICKS_PER_POINT = 4;
const MODEL_VERSION = 2;
const MODEL_KEY = 'fp_mediapipe_gaze_model_v2';
const VIDEO_ID = 'fpGazeVideo';
const FEATURE_HISTORY_LIMIT = 12;
const CALIBRATION_AVERAGE_FRAMES = 6;
const ONE_EURO_MIN_CUTOFF = 0.9;
const ONE_EURO_BETA = 0.12;
const ONE_EURO_D_CUTOFF = 1.0;

function meanLandmark(points, indexes) {
  return indexes.reduce(
    (acc, index) => ({
      x: acc.x + points[index].x / indexes.length,
      y: acc.y + points[index].y / indexes.length,
    }),
    { x: 0, y: 0 }
  );
}

function invertMatrix(matrix) {
  const n = matrix.length;
  const augmented = matrix.map((row, i) => [
    ...row,
    ...Array.from({ length: n }, (_, j) => (i === j ? 1 : 0)),
  ]);

  for (let col = 0; col < n; col += 1) {
    let pivot = col;
    for (let row = col + 1; row < n; row += 1) {
      if (Math.abs(augmented[row][col]) > Math.abs(augmented[pivot][col])) pivot = row;
    }
    if (Math.abs(augmented[pivot][col]) < 1e-8) {
      throw new Error('Calibration matrix is singular; recalibrate with wider eye movement.');
    }
    [augmented[col], augmented[pivot]] = [augmented[pivot], augmented[col]];

    const divisor = augmented[col][col];
    for (let j = 0; j < n * 2; j += 1) augmented[col][j] /= divisor;

    for (let row = 0; row < n; row += 1) {
      if (row === col) continue;
      const factor = augmented[row][col];
      for (let j = 0; j < n * 2; j += 1) {
        augmented[row][j] -= factor * augmented[col][j];
      }
    }
  }

  return augmented.map(row => row.slice(n));
}

function fitLinearModel(samples) {
  if (samples.length < 8) throw new Error('Need at least 8 calibration samples.');

  const featureCount = samples[0].features.length;
  const xtx = Array.from({ length: featureCount }, () => Array(featureCount).fill(0));
  const xtyX = Array(featureCount).fill(0);
  const xtyY = Array(featureCount).fill(0);

  samples.forEach(sample => {
    sample.features.forEach((left, i) => {
      xtyX[i] += left * sample.x;
      xtyY[i] += left * sample.y;
      sample.features.forEach((right, j) => {
        xtx[i][j] += left * right;
      });
    });
  });

  for (let i = 0; i < featureCount; i += 1) xtx[i][i] += 0.001;

  const inv = invertMatrix(xtx);
  const coeffX = inv.map(row => row.reduce((sum, value, i) => sum + value * xtyX[i], 0));
  const coeffY = inv.map(row => row.reduce((sum, value, i) => sum + value * xtyY[i], 0));
  if (!coeffX.every(Number.isFinite) || !coeffY.every(Number.isFinite)) {
    throw new Error('Calibration produced invalid coefficients. Recalibrate with steadier clicks.');
  }
  return { version: MODEL_VERSION, featureCount, coeffX, coeffY };
}

function dot(a, b) {
  if (a.length !== b.length) {
    throw new Error(`Gaze model feature mismatch: model has ${b.length}, tracker produced ${a.length}. Recalibrate.`);
  }
  return a.reduce((sum, value, i) => sum + value * b[i], 0);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function expandFeatures(base) {
  const [lx, rx, gx, ly, ry, gy, noseX, noseY, faceScale, faceTilt] = base;
  return [
    1,
    lx,
    rx,
    gx,
    ly,
    ry,
    gy,
    noseX,
    noseY,
    faceScale,
    faceTilt,
    gx * gy,
    lx * ly,
    rx * ry,
    noseX * gx,
    noseY * gy,
    faceScale * gx,
    faceScale * gy,
    faceTilt * gx,
    faceTilt * gy,
    gx * gx,
    gy * gy,
    noseX * noseX,
    noseY * noseY,
  ];
}

function averageFeatures(history) {
  if (history.length < CALIBRATION_AVERAGE_FRAMES) {
    throw new Error(`Need ${CALIBRATION_AVERAGE_FRAMES} stable iris frames before recording this calibration point.`);
  }
  const recent = history.slice(-CALIBRATION_AVERAGE_FRAMES);
  return recent[0].map((_, i) => (
    recent.reduce((sum, features) => sum + features[i], 0) / recent.length
  ));
}

function alpha(cutoff, dt) {
  const tau = 1 / (2 * Math.PI * cutoff);
  return 1 / (1 + tau / dt);
}

function smoothValue(current, previous, alphaValue) {
  return alphaValue * current + (1 - alphaValue) * previous;
}

function makeOneEuroFilter() {
  return {
    lastTime: null,
    x: null,
    y: null,
    dx: 0,
    dy: 0,
  };
}

function filterPoint(filter, x, y, timestamp) {
  if (filter.lastTime === null) {
    filter.lastTime = timestamp;
    filter.x = x;
    filter.y = y;
    return { x, y };
  }

  const dt = Math.max(1 / 120, (timestamp - filter.lastTime) / 1000);
  filter.lastTime = timestamp;

  const rawDx = (x - filter.x) / dt;
  const rawDy = (y - filter.y) / dt;
  const dAlpha = alpha(ONE_EURO_D_CUTOFF, dt);
  filter.dx = smoothValue(rawDx, filter.dx, dAlpha);
  filter.dy = smoothValue(rawDy, filter.dy, dAlpha);

  const speed = Math.hypot(filter.dx, filter.dy);
  const cutoff = ONE_EURO_MIN_CUTOFF + ONE_EURO_BETA * speed;
  const xAlpha = alpha(cutoff, dt);
  filter.x = smoothValue(x, filter.x, xAlpha);
  filter.y = smoothValue(y, filter.y, xAlpha);
  return { x: filter.x, y: filter.y };
}

function parseSavedModel(rawModel) {
  const model = JSON.parse(rawModel);
  if (
    model?.version !== MODEL_VERSION ||
    !Array.isArray(model.coeffX) ||
    !Array.isArray(model.coeffY) ||
    model.coeffX.length !== model.coeffY.length ||
    model.coeffX.length !== model.featureCount
  ) {
    throw new Error('Saved iris calibration model is incompatible. Recalibrate.');
  }
  return model;
}

function extractGazeFeatures(landmarks) {
  if (!landmarks || landmarks.length < 478) {
    throw new Error('MediaPipe did not return refined iris landmarks.');
  }

  const leftIris = meanLandmark(landmarks, [468, 469, 470, 471, 472]);
  const rightIris = meanLandmark(landmarks, [473, 474, 475, 476, 477]);
  const leftOuter = landmarks[33];
  const leftInner = landmarks[133];
  const rightInner = landmarks[362];
  const rightOuter = landmarks[263];
  const leftTop = landmarks[159];
  const leftBottom = landmarks[145];
  const rightTop = landmarks[386];
  const rightBottom = landmarks[374];
  const nose = landmarks[1];

  const leftWidth = Math.max(0.001, leftInner.x - leftOuter.x);
  const rightWidth = Math.max(0.001, rightOuter.x - rightInner.x);
  const leftHeight = Math.max(0.001, leftBottom.y - leftTop.y);
  const rightHeight = Math.max(0.001, rightBottom.y - rightTop.y);

  const lx = (leftIris.x - leftOuter.x) / leftWidth;
  const rx = (rightIris.x - rightInner.x) / rightWidth;
  const ly = (leftIris.y - leftTop.y) / leftHeight;
  const ry = (rightIris.y - rightTop.y) / rightHeight;
  const faceScale = Math.hypot(rightOuter.x - leftOuter.x, rightOuter.y - leftOuter.y);
  const faceTilt = Math.atan2(rightOuter.y - leftOuter.y, rightOuter.x - leftOuter.x);

  return expandFeatures([lx, rx, (lx + rx) / 2, ly, ry, (ly + ry) / 2, nose.x, nose.y, faceScale, faceTilt]);
}

export default function IrisTrackerController({
  onGazeUpdate,
  onTrackingPoint,
  setTrackingActive,
  setCalibrationProgress,
}) {
  const faceMeshRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const frameRef = useRef(null);
  const latestFeatures = useRef(null);
  const featureHistory = useRef([]);
  const latestModel = useRef(null);
  const calibrationSamples = useRef([]);
  const clickCountsRef = useRef({});
  const pointFilter = useRef(makeOneEuroFilter());
  const running = useRef(false);

  const [loading, setLoading] = useState(false);
  const [calibrating, setCalibrating] = useState(false);
  const [cameraStopped, setCameraStopped] = useState(false);
  const [clickCounts, setClickCounts] = useState({});
  const [permissionError, setPermissionError] = useState(null);
  const [calibrationPoints, setCalibrationPoints] = useState(FALLBACK_CALIBRATION_POINTS);

  useEffect(() => {
    try {
      const savedModel = localStorage.getItem(MODEL_KEY);
      if (savedModel) {
        latestModel.current = parseSavedModel(savedModel);
        setCameraStopped(true);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setPermissionError(message);
    }

    return () => {
      stopCamera();
    };
    // stopCamera reads refs directly and is safe for unmount cleanup.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ensureFaceMesh = async () => {
    if (!window.FaceMesh) {
      throw new Error('MediaPipe FaceMesh script is not loaded.');
    }
    if (faceMeshRef.current) return faceMeshRef.current;

    const faceMesh = new window.FaceMesh({
      locateFile: file => `/mediapipe/face_mesh/${file}`,
    });
    faceMesh.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.7,
      minTrackingConfidence: 0.7,
    });
    faceMesh.onResults(results => {
      const landmarks = results.multiFaceLandmarks?.[0];
      if (!landmarks) {
        latestFeatures.current = null;
        featureHistory.current = [];
        return;
      }
      const features = extractGazeFeatures(landmarks);
      latestFeatures.current = features;
      featureHistory.current = [...featureHistory.current, features].slice(-FEATURE_HISTORY_LIMIT);
    });
    faceMeshRef.current = faceMesh;
    return faceMesh;
  };

  const ensureVideo = async () => {
    if (!videoRef.current) {
      const video = document.createElement('video');
      video.id = VIDEO_ID;
      video.autoplay = true;
      video.muted = true;
      video.playsInline = true;
      video.style.position = 'fixed';
      video.style.left = '-9999px';
      video.style.top = '-9999px';
      video.style.width = '1px';
      video.style.height = '1px';
      document.body.appendChild(video);
      videoRef.current = video;
    }

    if (!streamRef.current) {
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 30, max: 30 },
        },
        audio: false,
      });
      videoRef.current.srcObject = streamRef.current;
      await videoRef.current.play();
    }

    return videoRef.current;
  };

  const emitPrediction = () => {
    if (!latestFeatures.current || !latestModel.current) return;
    if (latestModel.current.featureCount !== latestFeatures.current.length) {
      throw new Error(`Gaze model feature mismatch: model has ${latestModel.current.featureCount}, tracker produced ${latestFeatures.current.length}. Recalibrate.`);
    }
    const x = clamp(dot(latestFeatures.current, latestModel.current.coeffX), 0, window.innerWidth);
    const y = clamp(dot(latestFeatures.current, latestModel.current.coeffY), 0, window.innerHeight);
    const timestamp = performance.now();
    const point = filterPoint(pointFilter.current, x, y, timestamp);
    onTrackingPoint(point.x, point.y);
    onGazeUpdate(point.x, point.y, timestamp);
  };

  const runFrameLoop = async () => {
    if (!running.current || !videoRef.current || !faceMeshRef.current) return;
    try {
      await faceMeshRef.current.send({ image: videoRef.current });
      emitPrediction();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setPermissionError(message);
      running.current = false;
      setTrackingActive(false);
    } finally {
      if (running.current) frameRef.current = requestAnimationFrame(runFrameLoop);
    }
  };

  const startCamera = async () => {
    setLoading(true);
    setPermissionError(null);
    try {
      await ensureFaceMesh();
      await ensureVideo();
      if (!running.current) {
        running.current = true;
        frameRef.current = requestAnimationFrame(runFrameLoop);
      }
      setCameraStopped(false);
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setPermissionError(message);
      setTrackingActive(false);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const startCalibration = async () => {
    if (!await startCamera()) return;
    calibrationSamples.current = [];
    featureHistory.current = [];
    latestFeatures.current = null;
    latestModel.current = null;
    pointFilter.current = makeOneEuroFilter();
    // Keep the previous saved model until a new calibration succeeds.
    setTrackingActive(false);
    const points = buildCalibrationPoints();
    setCalibrationPoints(points);
    setCalibrating(true);
    setCalibrationProgress(0);
    const counts = {};
    points.forEach(point => { counts[point.id] = 0; });
    clickCountsRef.current = counts;
    setClickCounts(counts);
  };

  const resumeTracking = async () => {
    try {
      const savedModel = localStorage.getItem(MODEL_KEY);
      if (!savedModel) throw new Error('No saved MediaPipe calibration model. Calibrate first.');
      latestModel.current = parseSavedModel(savedModel);
      pointFilter.current = makeOneEuroFilter();
      if (!await startCamera()) return;
      setTrackingActive(true);
      setCalibrationProgress(null);
    } catch (err) {
      setPermissionError(err instanceof Error ? err.message : String(err));
    }
  };

  const stopCamera = () => {
    running.current = false;
    if (frameRef.current) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.remove();
      videoRef.current = null;
    }

    latestFeatures.current = null;
    featureHistory.current = [];
    pointFilter.current = makeOneEuroFilter();
    setTrackingActive(false);
    setCalibrating(false);
    setCalibrationProgress(null);
    setCameraStopped(true);
  };

  const handlePointClick = (point) => {
    if (!latestFeatures.current) {
      setPermissionError('No face/iris landmarks detected. Keep your face centered and try again.');
      return;
    }

    const currentClicks = clickCountsRef.current[point.id] || 0;
    if (currentClicks >= CLICKS_PER_POINT) return;

    const x = Math.round((point.left / 100) * window.innerWidth);
    const y = Math.round((point.top / 100) * window.innerHeight);
    let features;
    try {
      features = averageFeatures(featureHistory.current);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setPermissionError(message);
      return;
    }
    calibrationSamples.current.push({ features, x, y });

    setPermissionError(null);
    const updated = { ...clickCountsRef.current, [point.id]: currentClicks + 1 };
    clickCountsRef.current = updated;
    setClickCounts(updated);
    const total = Object.values(updated).reduce((a, b) => a + b, 0);
    const required = calibrationPoints.length * CLICKS_PER_POINT;
    setCalibrationProgress((total / required) * 100);

    if (total >= required) {
      try {
        const model = fitLinearModel(calibrationSamples.current);
        latestModel.current = model;
        pointFilter.current = makeOneEuroFilter();
        setCalibrating(false);
        setTrackingActive(true);
        setCalibrationProgress(null);
        setPermissionError(null);
        try {
          localStorage.setItem(MODEL_KEY, JSON.stringify(model));
        } catch {
          setPermissionError('Calibration complete. Tracking is active, but this browser could not save it for next time.');
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setPermissionError(message);
      }
    }
  };

  const renderButtons = () => {
    if (!running.current && !cameraStopped) {
      return (
        <button onClick={startCalibration} disabled={loading} className="sidebar-btn" style={{ background: loading ? 'transparent' : 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: 'var(--radius-pill)', fontSize: '0.8rem' }}>
          {loading ? <RefreshCw size={13} className="animate-spin" /> : <Camera size={13} />}
          {loading ? 'Starting...' : 'Calibrate Iris Tracker'}
        </button>
      );
    }

    if (cameraStopped) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <button onClick={resumeTracking} disabled={loading} className="sidebar-btn" style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: 'var(--radius-pill)', fontSize: '0.8rem' }}>
            {loading ? <RefreshCw size={13} className="animate-spin" /> : <Play size={13} />}
            {loading ? 'Starting...' : 'Resume Iris Tracking'}
          </button>
          <button onClick={startCalibration} disabled={loading} className="sidebar-btn" style={{ fontSize: '0.8rem' }}>
            <RefreshCw size={13} />
            Re-Calibrate
          </button>
        </div>
      );
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <button onClick={stopCamera} className="sidebar-btn" style={{ color: 'var(--danger)', fontSize: '0.8rem' }}>
          <CameraOff size={13} />
          Stop Camera
        </button>
        <button onClick={startCalibration} className="sidebar-btn" style={{ fontSize: '0.8rem' }}>
          <RefreshCw size={13} />
          Re-Calibrate
        </button>
      </div>
    );
  };

  return (
    <>
      {permissionError && (
        <div style={{ fontSize: '0.7rem', color: 'var(--danger)', padding: '4px 8px', marginBottom: '4px' }}>
          {permissionError}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {renderButtons()}
      </div>
      {calibrating && (
        <div role="dialog" aria-modal="true" aria-labelledby="iris-calibration-title" style={{
          position: 'fixed', top: 0, left: 0,
          width: '100vw', height: '100vh',
          backgroundColor: 'rgba(5, 5, 10, 0.95)',
          zIndex: 99999,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          pointerEvents: 'auto',
        }}>
          <div style={{
            position: 'absolute', top: '10%', left: '50%', transform: 'translateX(-50%)',
            textAlign: 'center', width: 'min(420px, 65vw)',
            color: 'var(--text-primary)', fontSize: '0.8rem',
          }}>
            <h3 id="iris-calibration-title" style={{ margin: '0 0 4px' }}>Calibrate Iris Tracking</h3>
            <p style={{ margin: '0 0 4px' }}>
              Look at each dot and click it {CLICKS_PER_POINT} times. Keep your head still.
              Tracking starts automatically when every dot is complete.
            </p>
            <div role="status">
              {Object.values(clickCounts).reduce((sum, count) => sum + count, 0)} / {calibrationPoints.length * CLICKS_PER_POINT} clicks
            </div>
            {permissionError && <div role="alert" style={{ color: 'var(--danger)' }}>{permissionError}</div>}
          </div>
          <div style={{ position: 'absolute', bottom: '10%', display: 'flex', gap: '12px' }}>
            <button className="sidebar-btn" onClick={startCalibration} disabled={loading}>Start over</button>
            <button className="sidebar-btn" onClick={stopCamera}>Cancel calibration</button>
          </div>
          {calibrationPoints.map(point => {
            const clicks = clickCounts[point.id] || 0;
            const done = clicks >= CLICKS_PER_POINT;
            return (
              <button
                key={point.id}
                aria-label={`Calibration point ${point.id}: ${clicks} of ${CLICKS_PER_POINT} clicks`}
                onClick={() => handlePointClick(point)}
                disabled={done}
                style={{
                  position: 'absolute',
                  top: `${point.top}%`, left: `${point.left}%`,
                  transform: 'translate(-50%, -50%)',
                  width: '32px', height: '32px',
                  borderRadius: '50%',
                  backgroundColor: done ? 'var(--success)' : clicks > 0 ? 'var(--warning)' : 'var(--accent)',
                  border: '3px solid #fff',
                  boxShadow: done ? '0 0 15px var(--success)' : '0 0 15px var(--accent)',
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.7rem', fontWeight: 'bold', color: '#fff',
                  transition: 'all 0.2s',
                  zIndex: 100001,
                }}
              >
                {clicks}
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}
