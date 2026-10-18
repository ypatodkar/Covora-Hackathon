from models import GazeEvent

FLAG_SCORES = {
    "smooth":    1.0,
    "skim":     -0.3,
    "confusion": -0.5,
    "skipped":  -0.2,
}

_STOP = {
    'the','a','an','is','it','in','on','at','to','for','of','and','or','but',
    'what','how','why','when','where','who','which','this','that','these','those',
    'i','me','my','you','your','we','our','they','their','do','does','did',
    'can','could','would','should','will','may','might','with','from','about',
    'be','been','have','has','had','not','if','as','so','no','yes','tell','give',
    'make','show','explain','please','help','just','also','more','some','any',
}

def _extract_topic(message: str) -> str | None:
    for word in message.lower().split():
        clean = ''.join(c for c in word if c.isalpha())
        if len(clean) > 4 and clean not in _STOP:
            return clean
    return None

def compute_reward(gaze_events: list[GazeEvent]) -> float | None:
    if not gaze_events:
        return None

    # If >70% of zones are skipped the user wasn't reading — calibration noise, ignore.
    skipped_ratio = sum(1 for e in gaze_events if e.flag == "skipped") / len(gaze_events)
    if skipped_ratio > 0.7:
        return None

    scores = []
    for e in gaze_events:
        base = FLAG_SCORES.get(e.flag, 0)
        # Amplify confusion/skim signals by visit intensity — more re-reads = stronger penalty
        if e.flag in ("confusion", "skim") and e.visits > 2:
            base *= min(e.visits / 2.0, 3.0)
        scores.append(base)

    reward = sum(scores) / len(scores)
    return round(max(-1.0, min(1.0, reward)), 2)

def update_profile_from_reward(
    profile: dict, reward: float, gaze_events: list[GazeEvent], message: str = ""
) -> dict:
    updates = {}
    score = profile.get("complexity_score", 5)

    # Same calibration-noise guard: if reward was suppressed, skip profile updates too
    if gaze_events:
        skipped_ratio = sum(1 for e in gaze_events if e.flag == "skipped") / len(gaze_events)
        if skipped_ratio > 0.7:
            return updates

    # Complexity: move by 0.5 steps and require consistent signal before crossing integer
    # This prevents wild bouncing on a single turn
    if reward < -0.3:
        new_score = max(1, score - 1)
        updates["complexity_score"] = new_score
    elif reward > 0.5:
        new_score = min(10, score + 1)
        updates["complexity_score"] = new_score

    # Format: only switch after a strong signal, not any negative reward
    if reward < -0.4:
        updates["preferred_format"] = "bullets"
    elif reward > 0.6 and score >= 6:
        updates["preferred_format"] = "prose"

    # reads_to_end: true only if no zones were skipped
    skipped = [e for e in gaze_events if e.flag == "skipped"]
    updates["reads_to_end"] = len(skipped) == 0

    # Topic extraction on confusion turns
    if reward < 0 and message:
        topic = _extract_topic(message)
        if topic:
            existing = profile.get("topics_to_simplify", [])
            if topic not in existing:
                updates["topics_to_simplify"] = (existing + [topic])[-5:]

    confusion_zones = [e.zone for e in gaze_events if e.flag == "confusion"]
    if confusion_zones:
        updates["re_read_rate"] = round(len(confusion_zones) / len(gaze_events), 2)

    # Estimate words read from zones that were not skipped (EMA to smooth noise)
    # Use real word_count from each event (sent by frontend); fall back to 40 if missing (old data)
    read_events = [
        e for e in gaze_events
        if e.flag in ("smooth", "confusion", "skim") and "_w" not in e.zone
    ]
    if read_events:
        estimated = sum(e.word_count if e.word_count > 0 else 40 for e in read_events)
        current   = profile.get("avg_words_read", 200)
        updates["avg_words_read"] = round(current * 0.7 + estimated * 0.3)

    return updates
