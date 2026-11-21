"""
Verification tests for the ASF model. Run with:  python -m pytest -q
Each test checks one rule of the model.
"""
import math
from dataclasses import replace

from asf_model import (ALLOWED_TRANSITIONS, CONTACT_DISTANCE, MARGIN, E, I, R, D, S, Settings, Simulation,
                       infection_probability, run_simulation)

SMALL = Settings(days=40)


def test_initial_infections():
    """The run starts with exactly the requested number of infected pigs, all in Pen 1."""
    for k in (1, 2, 5):
        sim = Simulation(replace(SMALL, initial_infected=k))
        infected = [p for p in sim.pigs if p.state == E]
        assert len(infected) == k
        assert all(p.pen == 0 for p in infected)


def test_population_is_conserved():
    """S + E + I + R + D + X always equals the number of pigs."""
    result = run_simulation(SMALL)
    for day in result.daily:
        assert day["S"] + day["E"] + day["I"] + day["R"] + day["D"] + day["X"] == SMALL.num_pigs


def test_no_transmission_when_rates_are_zero():
    """With both transmission rates at 0, nobody except the initial pigs gets infected."""
    result = run_simulation(replace(SMALL, direct_rate=0, indirect_rate=0))
    assert result.summary["total_infected"] == SMALL.initial_infected


def test_indirect_off_means_no_indirect_infections():
    result = run_simulation(replace(SMALL, indirect_on=False))
    assert result.summary["indirect_infections"] == 0


def test_direct_off_means_no_direct_infections():
    result = run_simulation(replace(SMALL, direct_rate=0))
    assert result.summary["direct_infections"] == 0


def test_same_seed_gives_same_result():
    a = run_simulation(replace(SMALL, seed=7))
    b = run_simulation(replace(SMALL, seed=7))
    c = run_simulation(replace(SMALL, seed=8))
    assert a.daily == b.daily and a.frames == b.frames
    assert a.daily != c.daily


def test_probability_is_between_0_and_1():
    for hazard in (-5, 0, 0.001, 0.5, 1, 10, 1000, float("nan")):
        p = infection_probability(hazard)
        assert 0 <= p <= 1
    assert infection_probability(0) == 0
    assert math.isclose(infection_probability(1), 1 - math.exp(-1))


def test_only_allowed_state_changes():
    """Every day-to-day change of a pig's state is one of the allowed transitions."""
    result = run_simulation(replace(SMALL, isolation_on=True, recovery_prob=0.3))
    for before, after in zip(result.states, result.states[1:]):
        for a, b in zip(before.upper(), after.upper()):
            assert a == b or b in ALLOWED_TRANSITIONS[a], f"{a} -> {b}"


def test_pigs_stay_inside_pens():
    """Every recorded position is inside a pen or the isolation pen (pigs never cross fences)."""
    sim = Simulation(replace(SMALL, movement_speed=3, isolation_on=True))
    result = sim.run()
    areas = result.pens + [result.isolation_pen]
    for day_frames in result.frames:
        for frame in day_frames:
            for k in range(0, len(frame), 2):
                x, z = frame[k], frame[k + 1]
                assert any(a["min_x"] + MARGIN - 0.01 <= x <= a["max_x"] - MARGIN + 0.01 and
                           a["min_z"] + MARGIN - 0.01 <= z <= a["max_z"] - MARGIN + 0.01 for a in areas)


def test_isolated_pigs_have_no_contacts():
    """An isolated infectious pig cannot touch a healthy pig, even at the same spot."""
    sim = Simulation(replace(SMALL, initial_infected=1))
    healthy = next(p for p in sim.pigs if p.state == S and p.pen == 0)
    sick = next(p for p in sim.pigs if p.state == E)
    sick.state = I
    sick.x, sick.z = healthy.x, healthy.z
    contacts = {}
    sim.count_contacts(contacts)
    assert contacts.get(healthy.id) == 1
    sick.isolated = True
    contacts = {}
    sim.count_contacts(contacts)
    assert healthy.id not in contacts
    assert CONTACT_DISTANCE > 0


def test_recovery_probability():
    """Recovery probability 0 -> nobody recovers; 1 -> nobody dies."""
    long = replace(SMALL, days=80)
    assert run_simulation(replace(long, recovery_prob=0.0)).summary["total_recovered"] == 0
    assert run_simulation(replace(long, recovery_prob=1.0)).summary["total_deaths"] == 0


def test_biosecurity_reduces_spread_on_average():
    """Behaviour check: over 10 matched seeds, high biosecurity gives fewer infections."""
    low = [run_simulation(replace(SMALL, seed=s, biosecurity=0.0)).summary["total_infected"] for s in range(10)]
    high = [run_simulation(replace(SMALL, seed=s, biosecurity=0.9)).summary["total_infected"] for s in range(10)]
    assert sum(high) < sum(low)
