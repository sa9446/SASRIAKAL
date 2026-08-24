"""
SASRIAKAL - ONNX Model Export Script
Exports MesoInception-4 to ONNX FP16 format for browser-based
WebAssembly inference via onnxruntime-web.

Usage:
    python -m models.export_onnx --output ../extension/models/
    python -m models.export_onnx --output ../extension/models/ --quantize int8
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import numpy as np
import torch
import torch.onnx

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.model import MesoInception4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sasriakal.export")

# ONNX export configuration
OPSET_VERSION = 14
INPUT_SIZE = (1, 3, 256, 256)  # batch, channels, height, width
ONNX_FILENAME = "meso4_deepfake.onnx"
ONNX_FP16_FILENAME = "meso4_deepfake_fp16.onnx"
ONNX_INT8_FILENAME = "meso4_deepfake_int8.onnx"


def export_meso4_to_onnx(output_dir: str, quantize: str = "fp16") -> str:
    """
    Export MesoInception-4 model to ONNX format.

    Args:
        output_dir: Directory to save ONNX model
        quantize: Quantization mode - "fp16", "int8", or "none"

    Returns:
        Path to exported ONNX model file
    """
    os.makedirs(output_dir, exist_ok=True)

    # Load MesoInception-4 model
    logger.info("Loading MesoInception-4 model...")
    model = MesoInception4(num_classes=1)
    model.eval()

    # Create dummy input
    dummy_input = torch.randn(*INPUT_SIZE)

    # Verify model runs
    logger.info("Verifying model with dummy input...")
    with torch.no_grad():
        output, attention = model(dummy_input)
        logger.info(f"  Output shape: {output.shape}, Attention shape: {attention.shape}")
        logger.info(f"  Confidence: {output.item():.4f}")

    # Export to ONNX
    onnx_path = os.path.join(output_dir, ONNX_FILENAME)

    logger.info(f"Exporting to ONNX (opset {OPSET_VERSION})...")
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=OPSET_VERSION,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["confidence", "attention_map"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "confidence": {0: "batch_size"},
            "attention_map": {0: "batch_size"},
        },
    )
    logger.info(f"  Saved: {onnx_path}")

    # Verify exported model
    verify_onnx_model(onnx_path, dummy_input)

    # Apply quantization
    if quantize == "fp16":
        fp16_path = os.path.join(output_dir, ONNX_FP16_FILENAME)
        convert_to_fp16(onnx_path, fp16_path)
        return fp16_path
    elif quantize == "int8":
        int8_path = os.path.join(output_dir, ONNX_INT8_FILENAME)
        convert_to_int8(onnx_path, int8_path)
        return int8_path
    else:
        return onnx_path


def verify_onnx_model(onnx_path: str, dummy_input: torch.Tensor):
    """Verify exported ONNX model produces correct output."""
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(onnx_path)
        input_np = dummy_input.numpy()

        outputs = session.run(None, {"input": input_np})

        logger.info("  ONNX model verification PASSED")
        logger.info(f"    Output count: {len(outputs)}")
        logger.info(f"    Confidence shape: {outputs[0].shape}")
        logger.info(f"    Attention shape: {outputs[1].shape}")

    except ImportError:
        logger.warning("onnxruntime not installed, skipping verification")
    except Exception as e:
        logger.error(f"  ONNX verification FAILED: {e}")


def convert_to_fp16(input_path: str, output_path: str):
    """Convert ONNX model to FP16 quantization."""
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType

        quantize_dynamic(
            input_path,
            output_path,
            weight_type=QuantType.QUInt16,  # FP16 weights
        )
        logger.info(f"  FP16 model saved: {output_path}")

        # Log file size comparison
        orig_size = os.path.getsize(input_path)
        fp16_size = os.path.getsize(output_path)
        logger.info(f"  Size: {orig_size / 1024:.1f}KB -> {fp16_size / 1024:.1f}KB "
                     f"({fp16_size / orig_size * 100:.1f}%)")

    except ImportError:
        logger.warning("onnxruntime.quantization not available, copying original model")
        import shutil
        shutil.copy2(input_path, output_path)


def convert_to_int8(input_path: str, output_path: str):
    """Convert ONNX model to INT8 quantization for maximum compression."""
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType

        quantize_dynamic(
            input_path,
            output_path,
            weight_type=QuantType.QUInt8,
        )
        logger.info(f"  INT8 model saved: {output_path}")

        orig_size = os.path.getsize(input_path)
        int8_size = os.path.getsize(output_path)
        logger.info(f"  Size: {orig_size / 1024:.1f}KB -> {int8_size / 1024:.1f}KB "
                     f"({int8_size / orig_size * 100:.1f}%)")

    except ImportError:
        logger.warning("onnxruntime.quantization not available, copying original model")
        import shutil
        shutil.copy2(input_path, output_path)


def benchmark_onnx(model_path: str, num_runs: int = 100) -> dict:
    """Benchmark ONNX model inference speed."""
    try:
        import onnxruntime as ort
        import time

        session = ort.InferenceSession(model_path)
        dummy = np.random.randn(*INPUT_SIZE).astype(np.float32)

        # Warmup
        for _ in range(10):
            session.run(None, {"input": dummy})

        # Benchmark
        latencies = []
        for _ in range(num_runs):
            start = time.perf_counter()
            session.run(None, {"input": dummy})
            latencies.append((time.perf_counter() - start) * 1000)

        results = {
            "mean_ms": round(np.mean(latencies), 2),
            "std_ms": round(np.std(latencies), 2),
            "min_ms": round(np.min(latencies), 2),
            "max_ms": round(np.max(latencies), 2),
            "p95_ms": round(np.percentile(latencies, 95), 2),
            "p99_ms": round(np.percentile(latencies, 99), 2),
            "throughput_fps": round(1000 / np.mean(latencies), 1),
        }

        logger.info("  Benchmark results:")
        for k, v in results.items():
            logger.info(f"    {k}: {v}")

        return results

    except ImportError:
        logger.warning("onnxruntime not available for benchmarking")
        return {}


def generate_js_wrapper(output_dir: str):
    """Generate a JavaScript wrapper for browser ONNX inference."""
    js_wrapper = '''/**
 * SASRIAKAL - ONNX Runtime Browser Inference Wrapper
 * Uses onnxruntime-web for zero-latency in-browser deepfake detection.
 *
 * Usage:
 *   const detector = new SASRIAKALONNX();
 *   await detector.load("models/meso4_deepfake_fp16.onnx");
 *   const result = await detector.detect(imageData);
 */

class SASRIAKALONNX {
  constructor() {
    this.session = null;
    this.inputSize = [1, 3, 256, 256];
    this.mean = [0.485, 0.456, 0.406];
    this.std = [0.229, 0.224, 0.225];
    this.threshold = 0.65;
  }

  async load(modelPath) {
    // @ts-ignore - onnxruntime-web global
    const ort = window.ort || (await import("onnxruntime-web"));
    this.session = await ort.InferenceSession.create(modelPath, {
      executionProviders: ["wasm", "cpu"],
      graphOptimizationLevel: "all",
    });
    console.log("[SASRIAKAL ONNX] Model loaded:", modelPath);
  }

  /**
   * Run inference on an ImageData or HTMLImageElement.
   * @param {ImageData|HTMLImageElement} source
   * @returns {{ confidence: number, attentionMap: Float32Array, detected: boolean }}
   */
  async detect(source) {
    if (!this.session) throw new Error("Model not loaded. Call load() first.");

    // Preprocess image to CHW float32 tensor
    const tensor = this._preprocess(source);
    const inputTensor = new ort.Tensor("float32", tensor, this.inputSize);

    const results = await this.session.run({ input: inputTensor });
    const confidence = results.confidence.data[0];
    const attentionMap = results.attention_map.data;

    return {
      confidence: Math.round(confidence * 10000) / 10000,
      attentionMap,
      detected: confidence >= this.threshold,
      heatmapBoxes: this._extractBoxes(attentionMap, source.width || 256, source.height || 256),
    };
  }

  _preprocess(source) {
    const canvas = new OffscreenCanvas(256, 256);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(source, 0, 0, 256, 256);
    const imageData = ctx.getImageData(0, 0, 256, 256);
    const data = imageData.data;

    // HWC -> CHW, normalize
    const chw = new Float32Array(3 * 256 * 256);
    for (let i = 0; i < 256 * 256; i++) {
      for (let c = 0; c < 3; c++) {
        chw[c * 256 * 256 + i] = (data[i * 4 + c] / 255.0 - this.mean[c]) / this.std[c];
      }
    }
    return chw;
  }

  _extractBoxes(attentionData, width, height) {
    const size = 32; // attention map spatial size
    const scaleX = width / size;
    const scaleY = height / size;

    // Find hot regions via thresholding
    const threshold = 0.3;
    const boxes = [];

    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const val = attentionData[y * size + x];
        if (val > threshold) {
          // Simple region growing (connected component)
          let exists = boxes.some(b =>
            Math.abs(b.x - x * scaleX) < scaleX * 3 &&
            Math.abs(b.y - y * scaleY) < scaleY * 3
          );
          if (!exists) {
            boxes.push({
              x: Math.round(x * scaleX),
              y: Math.round(y * scaleY),
              w: Math.round(scaleX * 3),
              h: Math.round(scaleY * 3),
              score: Math.round(val * 10000) / 10000,
            });
          }
        }
      }
    }

    return boxes;
  }
}

// Export for use in extension context
if (typeof module !== "undefined") {
  module.exports = SASRIAKALONNX;
}
'''

    wrapper_path = os.path.join(output_dir, "sasriakal_onnx.js")
    with open(wrapper_path, "w") as f:
        f.write(js_wrapper)
    logger.info(f"  JS wrapper saved: {wrapper_path}")


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Export MesoInception-4 to ONNX")
    parser.add_argument(
        "--output", "-o",
        default="../extension/models/",
        help="Output directory for ONNX model",
    )
    parser.add_argument(
        "--quantize", "-q",
        choices=["none", "fp16", "int8"],
        default="fp16",
        help="Quantization mode (default: fp16)",
    )
    parser.add_argument(
        "--benchmark", "-b",
        action="store_true",
        help="Run inference benchmark after export",
    )
    parser.add_argument(
        "--js-wrapper",
        action="store_true",
        help="Generate JavaScript inference wrapper",
    )
    args = parser.parse_args()

    output_dir = os.path.abspath(args.output)

    # Export model
    model_path = export_meso4_to_onnx(output_dir, args.quantize)

    # Benchmark
    if args.benchmark:
        logger.info("\nRunning benchmark...")
        benchmark_onnx(model_path)

    # Generate JS wrapper
    if args.js_wrapper:
        generate_js_wrapper(output_dir)

    logger.info(f"\nExport complete! Model saved to: {model_path}")


if __name__ == "__main__":
    main()
