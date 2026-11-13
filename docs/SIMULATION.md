# Simulation bench

The detection service can run without an accelerator, a camera or a fleet. The simulated accelerator is a function that takes the true boxes of a scene drawn from a fixed seed and writes them the way the chip does (the `hailo_nms_by_class` tensor of a letterboxed or stretched input, with the order and the unit of the contract), with a chosen amount of jitter, missed objects, invented ones and garbage rows. The real decoder brings them back to the pixels of the frame and the real mAP measure scores them. The simulated fleet is a set of nodes that report the model they loaded to a real registry on disk, and an owner who publishes signed bundles that nodes apply over the air, cut short or not.

## Run it

```
python -m pytest -q tests/test_simulation_bench.py
```

## What the scenarios check

| Scenario | What it shows |
|----------|---------------|
| a perfect chip in five frame sizes and both resize modes | the decoder gives back the true boxes to within two pixels |
| every order and unit of the contract | the same boxes come out |
| a chip without errors | the mAP is one |
| a chip that gets worse (jitter, misses, invented objects) | the mAP falls step by step and stays between zero and one |
| rows the chip garbles (not numbers, wrong length, score out of range) | they are dropped and change nothing |
| a threshold over or under every score | nothing or everything is kept |
| an answer of the wrong shape | refused, never guessed |
| the same seed twice, another seed | the run is reproducible and really depends on the seed |
| a fleet that reports old, tampered and unknown models | each node gets its verdict: current, outdated, wrong hash, wrong architecture, unknown model, changed contract |
| a node that updates | its newest report wins |
| a flood of nodes | the number of reports is bounded and the oldest is forgotten first |
| a registry edited by hand | it is found when it is loaded |
| a bundle cut short anywhere | refused and the node keeps what it had |
| an older bundle and a rollback | no quiet downgrade; the rollback puts the previous registry back |

The workflow named "Simulation bench" runs the bench on every change, so the simulated path has its own visible job.

## What it cannot show

A real accelerator, its real output on real images, the speed of either and a real network between the owner and the nodes need the hardware. The status of the repository therefore stays at "simulated" for the hardware row until a person has run the service on the bench.
