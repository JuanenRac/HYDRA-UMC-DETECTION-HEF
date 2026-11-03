# Bench tests

Every test below is **not executed**. The registry, the accuracy calculation and the signed bundles run only on files made for the tests; no model has been compiled for a Hailo accelerator and no accuracy has been measured on a real model. Write a result only after a person ran the step.

## What the software already covers (no accelerator needed)

- The unit tests check the mAP@0.5 calculation against hand-made detections and boxes, the gate `--min-accuracy-ratio` (a model with no measurement is rejected), the `io_contract` rules, the channels and the signed bundle checks.

## Setup

- A Hailo accelerator on a Compute Module 5 with the vendor runtime, a compiled `.hef` and the float model it came from.
- A validation split of real images with true boxes, never images used to train the model.
- A script that runs the compiled model over the split and writes the detections file read by `accuracy.py`.

## Steps

| # | Step | Expected result | Result |
|---|------|-----------------|--------|
| 1 | Run the reference (float) model over the split and compute its mAP@0.5. | A score is written to the entry as the reference. | not executed |
| 2 | Run the compiled model over the same split and run `registry record-accuracy`. | The `accuracy` block holds the new score next to the reference. | not executed |
| 3 | Run `registry validate --min-accuracy-ratio 0.9`. | A model below 90 percent of the reference is marked `rejected_accuracy`; one at or above is accepted. | not executed |
| 4 | Add a model with no measurement and validate with the gate on. | It is rejected. | not executed |
| 5 | Make a bundle, apply it with the public key on a second board, then with a wrong key and with a changed member. | Only the first is applied; the others are refused before any file is written. | not executed |
| 6 | Report the loaded model from a node with `serve --accept-loaded-reports`. | The registry shows the identity of the model that node runs. | not executed |

## What this bench cannot show

Quantisation loss on classes absent from the split, and speed on the accelerator; measure both before trusting a score for a different scene.
