# Contributing to HYDRA-UMC-DETECTION-HEF 🦾

We welcome contributions to the industrial model library of the HYDRA-UMC platform.

## Technology Stack
- **Frameworks**: PyTorch, Hailo Dataflow Compiler (DFC).
- **Models**: YOLOv8, YOLOv10, YOLOv11.
- **Hardware**: Hailo-8 (26 TOPS), Hailo-10 (40 TOPS).
- **Formats**: HEF, HAR, ONNX.

## Guidelines
1. **Model Accuracy**: All models must maintain a mAP@.50 higher than 95% after quantization.
2. **Latency**: Sub-10ms inference is mandatory for all industrial detection models.
3. **Quantization**: Use INT8 or INT4 quantization with Hailo's HAR files for performance.
4. **Synthetic Data**: If using synthetic data, ensure a diverse range of lighting and noise conditions.
