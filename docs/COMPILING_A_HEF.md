# Compiling a HEF by hand

This project registers, checksums and safe-loads compiled `.hef` models; it
does not compile them. Until a script that drives the Hailo Dataflow Compiler
exists (it waits for a Dataflow Compiler licence, see the end of this page),
a model is compiled by hand with Hailo's own tools and then added to the
registry. Nothing below has been run by this project: the commands follow
Hailo's documentation, so check them against the version of the Dataflow
Compiler you install.

## What you need

* The Hailo **Dataflow Compiler** (DFC) and, for the Model Zoo flow, the Hailo
  Model Zoo. Both are downloaded from Hailo's Developer Zone with a free
  account and run on x86-64 Linux (or in the Docker image Hailo provides).
  They are not redistributed here and are not a dependency of this project.
* A trained model exported to **ONNX** (for example a YOLO model exported from
  PyTorch), with the input size you will register (`--input-shape`).
* A **calibration set**: a few hundred representative images, resized to the
  model input and stored as a NumPy array (`calib.npy`, shape
  `N x H x W x 3`). Synthetic images from HYDRA-UMC-SYNTHETIC-DATA-GEN can
  be used, but real images of the target scene give a better quantization.
* The target architecture (`hailo8`, `hailo8l`, `hailo15h`, ...). It must match
  the `hailo_arch` you will write in the registry, because the safe-load gate
  refuses a model compiled for another architecture.

## Steps

1. **Parse** the ONNX model into a Hailo archive (`.har`):

   ```bash
   hailo parser onnx pcb-defect.onnx --net-name pcb-defect --hw-arch hailo8
   ```

2. **Optimize** (quantize) it with the calibration set:

   ```bash
   hailo optimize pcb-defect.har --hw-arch hailo8 --calib-set-path calib.npy
   ```

3. **Compile** the optimized archive into a `.hef`:

   ```bash
   hailo compiler pcb-defect_optimized.har
   ```

4. Rename the result to `<name>-<version>.hef` and copy it into the models
   folder, then register it. `registry add` computes the real sha256 and
   appends a validated entry:

   ```bash
   ./run.sh registry add --registry registry.json --models-dir models/ \
     --hef-path pcb-defect-0.3.0.hef --name pcb-defect --version 0.3.0 \
     --task detection --input-shape 640,640,3 \
     --classes solder_bridge,missing_component --hailo-arch hailo8
   ```

5. Check that it loads for the deployment target:

   ```bash
   ./run.sh registry load --registry registry.json --models-dir models/ \
     --name pcb-defect --target-arch hailo8
   ```

   Only `READY` means the checksum and the architecture both match.

## Keep a record

Write down, next to the model, the ONNX file and its hash, the DFC version,
the calibration set (or how it was generated), the architecture and the
quantization options. Without that the `.hef` cannot be regenerated, which is
the reason this page exists.

## Script with the Dataflow Compiler (not done)

A script that runs steps 1 to 4 in the Hailo Docker image, from an ONNX file
and a calibration folder, is deliberately not written yet: it needs a
Dataflow Compiler licence and download that are not available to this project.
It will be added when they are.
