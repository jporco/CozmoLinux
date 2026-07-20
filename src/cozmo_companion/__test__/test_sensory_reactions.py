from types import SimpleNamespace

from cozmo_companion.core.sensory_reactions import (
    MotionReactionDetector,
    SensorReaction,
)


def _cli(picked: bool, xyz: tuple[float, float, float]):
    return SimpleNamespace(
        robot_picked_up=picked,
        accel=SimpleNamespace(x=xyz[0], y=xyz[1], z=xyz[2]),
    )


def test_detecta_pegar_e_colocar() -> None:
    eventos = []
    det = MotionReactionDetector(eventos.append)
    det.update(_cli(False, (0, 0, 1)), agora=1)
    det.update(_cli(True, (0, 0, 1)), agora=2)
    det.update(_cli(False, (0, 0, 1)), agora=3)
    assert eventos == [SensorReaction.PICKED_UP, SensorReaction.PUT_DOWN]


def test_sacudida_exige_varios_picos(monkeypatch) -> None:
    monkeypatch.setenv("COZMO_SHAKE_JERK", "0.5")
    monkeypatch.setenv("COZMO_SHAKE_HITS", "3")
    eventos = []
    det = MotionReactionDetector(eventos.append)
    det.update(_cli(True, (0, 0, 1)), agora=10.0)
    det.update(_cli(True, (1, 0, 0)), agora=10.2)
    det.update(_cli(True, (-1, 0, 0)), agora=10.4)
    det.update(_cli(True, (1, 0, 0)), agora=10.6)
    assert eventos == [SensorReaction.SHAKE]


def test_movimento_suave_nao_e_sacudida(monkeypatch) -> None:
    monkeypatch.setenv("COZMO_SHAKE_JERK", "0.8")
    eventos = []
    det = MotionReactionDetector(eventos.append)
    det.update(_cli(True, (0, 0, 1)), agora=20.0)
    det.update(_cli(True, (0.1, 0, 0.95)), agora=20.2)
    det.update(_cli(True, (0.2, 0, 0.9)), agora=20.4)
    assert eventos == []
