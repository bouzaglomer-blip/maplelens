from maplelens.overlay import game_to_layer


def test_game_to_layer_125pct():
    assert game_to_layer(1250, 500, 1.25) == (1000.0, 400.0)
