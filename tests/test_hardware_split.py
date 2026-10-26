import pytest
from sol_uvix.hardware_orchestrator import HardwareWorkloadOrchestrator
from sol_uvix.codec import decode_uvix_slug


def test_hardware_status_inspection():
    orch = HardwareWorkloadOrchestrator()
    status = orch.get_hardware_status()

    assert "npu" in status
    assert "gpu" in status
    assert status["npu"]["tops"] == 50.0
    assert "NVIDIA" in status["gpu"]["device"]
    assert status["split_policy"] == "NPU_TEXT_GPU_VIDEO_RASTER"


def test_npu_text_offload():
    orch = HardwareWorkloadOrchestrator()
    res = orch.dispatch("text", {"prompt": "Analyze Solana bonding curve dynamics and UVIX slug", "max_tokens": 64})

    assert res["status"] == "COMPLETED"
    assert res["target_hardware"] == "AMD-XDNA2-NPU"
    assert "slug" in res
    assert res["slug"].startswith("UVIX::")

    decoded = decode_uvix_slug(res["slug"])
    assert decoded.source_platform == "AMD-XDNA2-NPU-Engine"
    assert decoded.raw_payload["data"]["status"] == "COMPLETED"


def test_gpu_video_transcode():
    orch = HardwareWorkloadOrchestrator()
    res = orch.dispatch("video", {"codec": "av1_nvenc", "resolution": "4k", "frames": 120})

    assert res["status"] == "COMPLETED"
    assert res["target_hardware"] == "NVIDIA-RTX-4070"
    assert res["codec"] == "av1_nvenc"
    assert "slug" in res

    decoded = decode_uvix_slug(res["slug"])
    assert decoded.source_platform == "NVIDIA-RTX4070-Engine"
    assert decoded.raw_payload["data"]["frames"] == 120


def test_gpu_raster_render():
    orch = HardwareWorkloadOrchestrator()
    res = orch.dispatch("raster", {"primitives": 100_000, "resolution": "1440p"})

    assert res["status"] == "COMPLETED"
    assert res["target_hardware"] == "NVIDIA-RTX-4070"
    assert "CUDA-RASTER" in res["metrics"]["engine_utilized"]
    assert "slug" in res
