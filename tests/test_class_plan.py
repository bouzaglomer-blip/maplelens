from maplelens.tools.class_helper.data import STATS, Band, Build
from maplelens.tools.class_helper.plan import Advice, ap_advice, band_at

B = Band(1, 200, {"DEX": (25, 0.0)}, "LUK")


def s(str_, dex, int_, luk):
    return dict(zip(STATS, (str_, dex, int_, luk), strict=True))


def test_holds_fill_first_then_the_main_stat():
    a = ap_advice(B, 20, s(4, 20, 4, 30), 10)
    assert a["DEX"] == Advice(add=5) and a["LUK"] == Advice(add=5)
    assert a["STR"] == a["INT"] == Advice()


def test_over_a_hold_puts_the_main_stat_behind():
    a = ap_advice(B, 20, s(4, 35, 4, 20), 0)
    assert a["DEX"] == Advice(over=10) and a["LUK"] == Advice(behind=10)


def test_short_points_still_go_to_the_hold_first():
    a = ap_advice(B, 20, s(4, 20, 4, 30), 3)
    assert a["DEX"] == Advice(add=3, behind=2) and a["LUK"] == Advice(over=2)


def test_stats_outside_the_plan_never_get_points_or_tags():
    a = ap_advice(B, 20, s(4, 25, 9, 30), 5)  # INT rolled 9 at the start
    assert a["INT"] == Advice() and a["LUK"] == Advice(add=5)


def test_growing_hold_and_band_lookup():
    grow = Band(1, 200, {"DEX": (0, 1.0)}, "LUK")
    assert ap_advice(grow, 30, s(4, 28, 4, 40), 2)["DEX"] == Advice(add=2)
    build = Build("x", (Band(1, 29, {}, "LUK"), grow), (), (), None, None)
    assert band_at(build, 29).to_level == 29 and band_at(build, 30) is grow
