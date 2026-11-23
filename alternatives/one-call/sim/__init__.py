"""Simulated-person harness for Daylight conversation loops.

Offline by default. `sim.person` holds the simulated people, `sim.run` drives a
conversation flow through `flow.turn(owner, payload)`, and `sim.graders` scores
a finished run. A live run costs money, needs the owner's clearance and is
never started by an agent; see `sim/README.md`.
"""
