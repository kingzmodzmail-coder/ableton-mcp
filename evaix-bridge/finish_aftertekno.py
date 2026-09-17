"""Place the recovered Aftertekno ending without replacing existing clips.

Run with Python 3. Reads the saved baseline, checks identities and overlaps,
and verifies placements. Re-running skips matching placements.
"""
import json
from pathlib import Path

from ableton_cmd import send_command

ROOT = Path(__file__).parent / "aftertekno-continuation"


def main():
    baseline = json.loads((ROOT / "before.json").read_text(encoding="utf-8"))
    current = send_command("get_session_snapshot", timeout=45)
    assert current["session"]["tempo"] == 126, "Unexpected tempo"
    assert len(current["tracks"]) == len(baseline["tracks"]), "Track list changed"
    start = max(c["end_time"] for t in baseline["tracks"] for c in t["arrangement_clips"])
    assert start == 456, "Unexpected original arrangement endpoint"
    # Full-mix reference (15) is deliberately excluded: stems already supply it.
    selected = {6: [0, 1, 2, 3, 6, 7, 8, 9, 11], 7: [0, 1, 2, 3, 6, 7, 8, 9]}
    plan = []
    for slot, tracks in selected.items():
        destination = start + (slot - 6) * 32
        for index in tracks:
            track = current["tracks"][index]
            old = baseline["tracks"][index]
            assert track["name"] == old["name"], "Track identity changed"
            clip = track["clip_slots"][slot]["clip"]
            assert clip["name"] == old["clip_slots"][slot]["clip"]["name"]
            assert clip["length"] == 32
            if clip.get("is_audio_clip"):
                assert Path(clip["file_path"]).is_file(), clip["file_path"]
            overlaps = [c for c in track["arrangement_clips"]
                        if c["start_time"] < destination + 32 and c["end_time"] > destination]
            matched = len(overlaps) == 1 and all(
                overlaps[0][k] == v for k, v in
                {"name": clip["name"], "start_time": destination, "end_time": destination + 32}.items())
            assert not overlaps or matched, "Existing material overlaps destination"
            plan.append({"track_index": index, "clip_index": slot,
                         "destination_time": destination, "name": clip["name"], "skip": matched})
    (ROOT / "placement-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    for item in plan:
        if not item["skip"]:
            send_command("duplicate_session_clip_to_arrangement",
                         {k: item[k] for k in ("track_index", "clip_index", "destination_time")})
        print("Placed", item["track_index"], item["name"], item["destination_time"], flush=True)
    after = send_command("get_session_snapshot", timeout=45)
    for item in plan:
        clips = after["tracks"][item["track_index"]]["arrangement_clips"]
        assert any(c["name"] == item["name"] and c["start_time"] == item["destination_time"]
                   and c["end_time"] == item["destination_time"] + 32 for c in clips)
    for index, track in enumerate(baseline["tracks"]):
        original = [{k: c[k] for k in ("name", "start_time", "end_time")}
                    for c in track["arrangement_clips"]]
        retained = [{k: c[k] for k in ("name", "start_time", "end_time")}
                    for c in after["tracks"][index]["arrangement_clips"] if c["start_time"] < start]
        assert original == retained, "Original arrangement changed"
    (ROOT / "after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
    send_command("switch_to_arrangement_view")
    send_command("set_current_song_time", {"time": start})
    print("Verified 17 clips; original arrangement retained; ending beats 456-520.")


if __name__ == "__main__":
    main()
