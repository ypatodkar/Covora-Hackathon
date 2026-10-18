import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import IrisTrackerController from './IrisTrackerController';

const MODEL_KEY = 'fp_mediapipe_gaze_model_v2';
let receiveResults;
let stopTrack;
let callbacks;

function feedFace(noseX = 0.5) {
  const landmarks = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
  landmarks[1] = { x: noseX, y: 0.5 };
  landmarks[33] = { x: 0.2, y: 0.4 };
  landmarks[133] = { x: 0.4, y: 0.4 };
  landmarks[362] = { x: 0.6, y: 0.4 };
  landmarks[263] = { x: 0.8, y: 0.4 };
  landmarks[159] = landmarks[386] = { x: 0.5, y: 0.3 };
  landmarks[145] = landmarks[374] = { x: 0.5, y: 0.6 };
  for (let i = 0; i < 6; i++) receiveResults({ multiFaceLandmarks: [landmarks] });
}

async function start() {
  render(<IrisTrackerController {...callbacks} />);
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Calibrate Iris Tracker' })));
}

function finishPoints() {
  for (let point = 1; point <= 13; point++) {
    const button = screen.getByRole('button', { name: new RegExp(`^Calibration point ${point}:`) });
    // Batched clicks also exercise the counter before React rerenders.
    act(() => { for (let i = 0; i < 4; i++) fireEvent.click(button); });
  }
}

beforeEach(() => {
  localStorage.clear();
  callbacks = {
    onGazeUpdate: vi.fn(), onTrackingPoint: vi.fn(),
    setTrackingActive: vi.fn(), setCalibrationProgress: vi.fn(),
  };
  stopTrack = vi.fn();
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }),
  } });
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
  vi.stubGlobal('FaceMesh', class {
    setOptions() {}
    onResults(fn) { receiveResults = fn; }
    async send() {}
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('iris calibration completion', () => {
  it('exits after all 52 accepted clicks and keeps the camera running for tracking', async () => {
    await start();
    expect(screen.getAllByRole('button', { name: /^Calibration point/ })).toHaveLength(13);
    feedFace();
    // One click on every point is not enough to finish.
    for (let point = 1; point <= 13; point++) {
      fireEvent.click(screen.getByRole('button', { name: new RegExp(`^Calibration point ${point}:`) }));
    }
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByRole('status').textContent).toBe('13 / 52 clicks');
    finishPoints();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(callbacks.setTrackingActive).toHaveBeenLastCalledWith(true);
    expect(callbacks.setCalibrationProgress).toHaveBeenLastCalledWith(null);
    const model = JSON.parse(localStorage.getItem(MODEL_KEY));
    expect(model.coeffX.every(Number.isFinite)).toBe(true);
    expect(model.coeffY.every(Number.isFinite)).toBe(true);
    expect(stopTrack).not.toHaveBeenCalled();
  });

  it('shows missing face errors inside the overlay without advancing', async () => {
    await start();
    fireEvent.click(screen.getByRole('button', { name: /^Calibration point 1:/ }));
    expect(screen.getByRole('alert').textContent).toContain('No face/iris landmarks');
    expect(screen.getByRole('status').textContent).toBe('0 / 52 clicks');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel calibration' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(stopTrack).toHaveBeenCalledOnce();
  });

  it('does not open calibration when camera permission is denied', async () => {
    navigator.mediaDevices.getUserMedia.mockRejectedValue(new Error('Camera permission denied'));
    await start();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByText('Camera permission denied')).toBeTruthy();
    expect(callbacks.setTrackingActive).not.toHaveBeenCalledWith(true);
  });

  it('finishes even if saving the model fails', async () => {
    await start();
    feedFace();
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage full'); });
    finishPoints();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(callbacks.setTrackingActive).toHaveBeenLastCalledWith(true);
    expect(screen.getByText(/Tracking is active, but this browser could not save/)).toBeTruthy();
  });

  it('restarts the click count without starting a second camera frame loop', async () => {
    await start();
    feedFace();
    fireEvent.click(screen.getByRole('button', { name: /^Calibration point 1:/ }));
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Start over' })));
    expect(screen.getByRole('status').textContent).toBe('0 / 52 clicks');
    expect(requestAnimationFrame).toHaveBeenCalledOnce();
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledOnce();
  });

  it('allows retry after a failed model fit at the last point', async () => {
    await start();
    feedFace(NaN);
    finishPoints();
    expect(screen.getByRole('alert').textContent).toContain('invalid coefficients');
    expect(callbacks.setTrackingActive).not.toHaveBeenCalledWith(true);
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Start over' })));
    feedFace();
    finishPoints();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(callbacks.setTrackingActive).toHaveBeenLastCalledWith(true);
  });
});
