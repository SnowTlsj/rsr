from pathlib import Path
import importlib.util
import sys


MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
SPEC = importlib.util.spec_from_file_location("serial_bridge_main", MODULE_PATH)
main = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = main
SPEC.loader.exec_module(main)


def test_parse_float_le():
    assert round(main.parse_float_le(bytes.fromhex("4D B9 BF 41")), 2) == 23.97


def test_parse_frame_sample():
    frame = main.parse_frame(main.sample_frame_bytes())
    assert frame.channel_values == [23.22, 24.53, 26.17, 23.91, 24.03]
    assert frame.distance_m == 10.01
    assert frame.alarm_channels == [0, 0, 0, 0, 0]


def test_assembler_half_packet():
    assembler = main.SerialFrameAssembler(main.FrameStats())
    sample = main.sample_frame_bytes()
    assembler.append(sample[:20])
    assert assembler.pop_frames() == []
    assembler.append(sample[20:])
    assert len(assembler.pop_frames()) == 1


def test_assembler_dirty_bytes_resync():
    assembler = main.SerialFrameAssembler(main.FrameStats())
    assembler.append(b"\x00\x01\x02" + main.sample_frame_bytes())
    assert len(assembler.pop_frames()) == 1


def test_payload_mapping():
    cfg = main.build_config(main.argparse.Namespace(self_check=False, port="", config="", log_file="", once=False, no_cache_replay=False, debug=False))
    agent = main.SerialIngestAgent(cfg, replay_cache=False)
    payload = agent._build_payload(main.parse_frame(main.sample_frame_bytes()))
    assert payload["telemetry"]["seed_total_g"] == 121.86
    assert payload["gps"]["lat"] == 42.829712
