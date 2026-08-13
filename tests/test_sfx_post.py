"""Post-processing is pure and runs without the ACE service.

Splitting the maths out of the HTTP call is the whole reason these are
testable -- and post-processing is the part that decides whether a generated
sound is usable at all.
"""

import sfx_gen


def test_trim_onset_removes_leading_silence():
    samples = [0] * 1000 + [10000, -10000] * 100
    assert len(sfx_gen.trim_onset(samples, rate=1000, lead_ms=0)) == 200


def test_trim_onset_keeps_a_lead_in():
    samples = [0] * 1000 + [10000] * 100
    assert len(sfx_gen.trim_onset(samples, rate=1000, lead_ms=10)) == 110


def test_trim_onset_never_runs_off_the_front():
    samples = [10000] * 50
    assert len(sfx_gen.trim_onset(samples, rate=1000, lead_ms=500)) == 50


def test_trim_onset_of_silence_is_unchanged():
    samples = [0] * 100
    assert sfx_gen.trim_onset(samples, rate=1000) == samples


def test_fade_out_ends_at_zero():
    faded = sfx_gen.fade_out([10000] * 1000, ms=100, rate=1000)
    assert faded[-1] == 0
    assert faded[0] == 10000


def test_fade_longer_than_the_clip_still_works():
    faded = sfx_gen.fade_out([10000] * 10, ms=500, rate=1000)
    assert len(faded) == 10
    assert faded[-1] == 0


def test_rms_dbfs_of_full_scale_square_is_zero():
    assert abs(sfx_gen.rms_dbfs([32767, -32767] * 100)) < 0.1


def test_rms_dbfs_of_silence_is_very_negative():
    assert sfx_gen.rms_dbfs([0] * 100) < -100


def test_normalize_raises_a_quiet_signal():
    louder = sfx_gen.normalize_to([100, -100] * 100, -17.0)
    assert abs(sfx_gen.rms_dbfs(louder) - (-17.0)) < 0.2


def test_normalize_never_clips():
    loud = [32000, -32000] * 100
    out = sfx_gen.normalize_to(loud, 0.0)
    assert all(-32768 <= s <= 32767 for s in out)


def test_soft_compress_lifts_quiet_detail():
    """A light rustle peaks high but its body is tiny; plain gain blows the
    peak before the body is audible."""
    out = sfx_gen.soft_compress([1000, 32000], amount=3.2)
    assert out[0] > 1000
    assert abs(out[1]) <= 32767


def test_soft_compress_never_clips():
    out = sfx_gen.soft_compress([32767, -32767, 30000], amount=5.0)
    assert all(-32768 <= s <= 32767 for s in out)


def test_soft_compress_preserves_sign():
    out = sfx_gen.soft_compress([-5000, 5000], amount=3.2)
    assert out[0] < 0 < out[1]


def test_truncate_cuts_to_length():
    assert len(sfx_gen.truncate([1] * 1000, seconds=0.3, rate=1000)) == 300


def test_truncate_leaves_short_clips_alone():
    assert len(sfx_gen.truncate([1] * 100, seconds=0.3, rate=1000)) == 100


def test_wav_roundtrip(tmp_path):
    path = tmp_path / "t.wav"
    samples = [0, 1000, -1000, 32767, -32768]
    sfx_gen.write_wav(path, samples, rate=22050)
    back, rate = sfx_gen.read_wav(path)
    assert rate == 22050
    assert back == samples


def test_process_chain_produces_a_usable_clip(tmp_path):
    """End to end on the shape ACE actually returns: leading silence, then a
    quiet body."""
    src = tmp_path / "raw.wav"
    samples = [0] * 4410 + [400, -400] * 11025
    sfx_gen.write_wav(src, samples, rate=44100)

    out = tmp_path / "clean.wav"
    report = sfx_gen.process(src, out, target_dbfs=-17.0, seconds=0.3)

    done, rate = sfx_gen.read_wav(out)
    assert len(done) == int(0.3 * rate)
    assert done[-1] == 0
    assert abs(report["dbfs_out"] - (-17.0)) < 1.5
    assert report["dbfs_in"] < report["dbfs_out"]
