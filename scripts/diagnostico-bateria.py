#!/usr/bin/env python3
"""Diagnóstico rápido: base, carga e bateria do Cozmo."""
import sys
import time

sys.path.insert(0, "/mnt/G/PROJETOS/cozmo-companion/src")

import pycozmo
from pycozmo import robot


def flags(cli):
    st = cli.robot_status
    nomes = []
    for flag, nome in robot.RobotStatusFlagNames.items():
        if st & flag:
            nomes.append(nome)
    return nomes


with pycozmo.connect(log_level="ERROR", robot_log_level="ERROR") as cli:
    for i in range(5):
        time.sleep(0.5)
        print(
            f"[{i+1}] {cli.battery_voltage:.3f}V | "
            f"flags={', '.join(flags(cli)) or 'nenhuma'}"
        )
