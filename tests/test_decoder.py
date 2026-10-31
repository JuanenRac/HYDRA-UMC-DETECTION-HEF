import copy

import pytest

from hydra_umc_detection_hef.decoder import DecodeError, decode_nms_by_class, letterbox_geometry

CONTRACT = {
    "input": {"layout": "NHWC", "color_order": "RGB", "dtype": "uint8", "normalization": "on-chip", "resize": "letterbox", "pad_value": 114},
    "output": {"format": "hailo_nms_by_class", "bbox_order": "ymin,xmin,ymax,xmax", "bbox_normalized": True, "nms_on_chip": True,
               "max_detections_per_class": 100, "score_threshold": 0.25, "iou_threshold": 0.45},
}
CLASSES = ["missing", "bridge"]
SHAPE = (640, 640, 3)


def _decode(output, contract=CONTRACT, frame=(1280, 720), **kwargs):
    return decode_nms_by_class(output, contract, input_shape=SHAPE, frame_size=frame, classes=CLASSES, **kwargs)


def test_letterbox_geometry_of_a_wide_frame():
    assert letterbox_geometry(1280, 720, 640, 640) == (0.5, 0.0, 140.0)
    assert letterbox_geometry(640, 640, 640, 640) == (1.0, 0.0, 0.0)
    assert letterbox_geometry(720, 1280, 640, 640) == (0.5, 140.0, 0.0)


def test_gold_box_is_mapped_back_to_the_frame():
    # the box (320,200)-(640,400) of a 1280x720 frame is (160,240)-(320,340) in the 640x640 letterboxed input
    out = [[[0.375, 0.25, 0.53125, 0.5, 0.9]], []]
    [det] = _decode(out)
    assert (det.class_id, det.label, det.score) == (0, "missing", 0.9)
    assert (det.x_min, det.y_min, det.x_max, det.y_max) == (320.0, 200.0, 640.0, 400.0)
    assert det.as_dict()["box"] == {"xMin": 320.0, "yMin": 200.0, "xMax": 640.0, "yMax": 400.0}


def test_xmin_first_order_gives_the_same_box():
    contract = copy.deepcopy(CONTRACT)
    contract["output"]["bbox_order"] = "xmin,ymin,xmax,ymax"
    [det] = _decode([[[0.25, 0.375, 0.5, 0.53125, 0.9]], []], contract)
    assert (det.x_min, det.y_min, det.x_max, det.y_max) == (320.0, 200.0, 640.0, 400.0)


def test_boxes_in_input_pixels_when_not_normalized():
    contract = copy.deepcopy(CONTRACT)
    contract["output"]["bbox_normalized"] = False
    [det] = _decode([[[240.0, 160.0, 340.0, 320.0, 0.8]], []], contract)
    assert (det.x_min, det.y_min, det.x_max, det.y_max) == (320.0, 200.0, 640.0, 400.0)


def test_stretch_scales_each_axis_alone():
    contract = copy.deepcopy(CONTRACT)
    contract["input"]["resize"] = "stretch"
    # 1280x720 stretched to 640x640: x halves, y shrinks to 8/9
    [det] = _decode([[[0.25, 0.25, 0.5, 0.5, 0.9]], []], contract)
    assert (det.x_min, det.x_max) == (320.0, 640.0)
    assert det.y_min == pytest.approx(180.0) and det.y_max == pytest.approx(360.0)


def test_low_score_and_bad_rows_are_dropped_not_repaired():
    rows = [
        [0.375, 0.25, 0.53125, 0.5, 0.2],  # under the contract threshold 0.25
        [0.375, 0.25, 0.53125, 0.5],  # four numbers
        [0.375, 0.25, 0.53125, float("nan"), 0.9],
        [0.375, 0.25, 0.53125, 0.5, 1.5],  # score above 1
        [0.375, True, 0.53125, 0.5, 0.9],
        "x",
        [0.375, 0.25, 0.375, 0.5, 0.9],  # no height
        [0.0, 0.0, 0.1, 0.1, 0.9],  # entirely inside the top padding: no area once clipped
    ]
    assert _decode([rows, []]) == []


def test_boxes_over_the_edge_are_clipped():
    [det] = _decode([[], [[0.2, 0.9, 0.95, 1.2, 0.7]]])
    assert det.x_max == 1280.0 and det.y_max <= 720.0 and det.y_min >= 0.0 and det.x_min < det.x_max


def test_sorted_by_score_and_capped_per_class():
    contract = copy.deepcopy(CONTRACT)
    contract["output"]["max_detections_per_class"] = 2
    out = [[[0.4, 0.3, 0.5, 0.4, 0.5], [0.4, 0.3, 0.5, 0.4, 0.9], [0.4, 0.3, 0.5, 0.4, 0.7]], [[0.4, 0.3, 0.5, 0.4, 0.8]]]
    assert [d.score for d in _decode(out, contract)] == [0.9, 0.8, 0.5]


def test_threshold_override_and_default():
    out = [[[0.375, 0.25, 0.53125, 0.5, 0.3]], []]
    assert len(_decode(out)) == 1
    assert _decode(out, score_threshold=0.5) == []
    contract = copy.deepcopy(CONTRACT)
    del contract["output"]["score_threshold"]
    assert len(_decode([[[0.375, 0.25, 0.53125, 0.5, 0.01]], []], contract)) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"output": [[]]},  # one class too few
        {"output": "x"},
        {"output": [[], 5]},
        {"frame": (0, 720)},
        {"score_threshold": 2.0},
        {"score_threshold": True},
    ],
)
def test_refuses_what_cannot_be_decoded(kwargs):
    kwargs = {"output": [[], []], **kwargs}
    output = kwargs.pop("output")
    with pytest.raises(DecodeError):
        _decode(output, **kwargs)


def test_refuses_other_formats_and_resizes():
    contract = copy.deepcopy(CONTRACT)
    contract["output"]["format"] = "raw_yolo"
    with pytest.raises(DecodeError):
        _decode([[], []], contract)
    contract = copy.deepcopy(CONTRACT)
    contract["input"]["resize"] = "crop"
    with pytest.raises(DecodeError):
        _decode([[], []], contract)
    with pytest.raises(DecodeError):
        _decode([[], []], {"input": {}})
