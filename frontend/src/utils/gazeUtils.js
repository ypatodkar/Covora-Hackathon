/**
 * Gaze utility functions for mapping coordinates and computing reading flags.
 */

/**
 * Maps screen coordinates (x, y) to the corresponding DOM element's data-zone.
 * @param {number} x - The horizontal gaze coordinate.
 * @param {number} y - The vertical gaze coordinate.
 * @returns {string|null} The line zone identifier (e.g., 'response_id:line_0') or null.
 */
export function getZoneAtGaze(x, y) {
  // Only Y matters — zones are horizontal paragraph strips.
  // Fix X to the chat area center so X prediction errors don't cause missed zones.
  const chatEl = document.getElementById('fp-chat-area');
  const lookupX = chatEl
    ? chatEl.getBoundingClientRect().left + chatEl.getBoundingClientRect().width / 2
    : x;
  const el = document.elementFromPoint(lookupX, y);
  if (el) {
    const zoneEl = el.closest('[data-zone]');
    if (zoneEl) return zoneEl.getAttribute('data-zone');
  }
  return null;
}

/**
 * Computes gaze events and assigns flags based on reading behavior.
 * Flags: 'smooth' | 'confusion' | 'skim' | 'skipped'
 * 
 * @param {string[]} allZones - List of all zone IDs present in the response.
 * @param {Object} zoneLog - Stable fixation timestamps per zone.
 * @returns {Array<{zone: string, visits: number, flag: string}>}
 */
// Each fixation log entry represents one interval of stable gaze
const LOG_INTERVAL_MS = 450;
// Conservative silent reading speed: 200 wpm = 300ms per word
// (range is 200–250 wpm, using lower end so slower readers aren't penalised)
const MS_PER_WORD = (60 / 200) * 1000;

/**
 * Computes the expected reading time for a line in ms.
 * Minimum is one log interval so a 1-word line isn't impossible to "pass".
 */
export function expectedReadMs(wordCount) {
  return Math.max(wordCount * MS_PER_WORD, LOG_INTERVAL_MS);
}

/**
 * Computes reading ratio: actual time spent / expected time to read.
 * ratio < 0.5  → skimmed (too fast)
 * ratio 0.5–2  → smooth (normal read)
 * ratio > 2    → confusion (re-reading, stuck)
 */
export function readingRatio(visits, wordCount) {
  if (visits === 0) return 0;
  return (visits * LOG_INTERVAL_MS) / expectedReadMs(wordCount);
}

export function computeGazeEvents(allZones, zoneLog, zoneWordCounts = {}) {
  return allZones.map(zone => {
    const visits    = (zoneLog[zone] || []).length;
    const wordCount = zoneWordCounts[zone] || 10;

    if (visits === 0) return { zone, visits: 0, flag: 'skipped', word_count: wordCount };

    const ratio = readingRatio(visits, wordCount);

    if (ratio < 0.5)  return { zone, visits, flag: 'skim',      word_count: wordCount };
    if (ratio <= 3.0) return { zone, visits, flag: 'smooth',    word_count: wordCount };
    return                   { zone, visits, flag: 'confusion', word_count: wordCount };
  });
}
