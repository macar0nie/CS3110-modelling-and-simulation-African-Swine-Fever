"""
ASF simulation model (agent-based, stochastic, discrete time).

Every pig is an agent with a position inside a pen and a disease state.
Each simulated day:
  1. Pigs walk around their pen (6 movement steps per day, one every 4 hours).
     After each step we count close contacts between healthy and infectious pigs.
  2. Every susceptible pig gets an infection probability for the day:
         P = 1 - exp(-(direct hazard + indirect hazard))
     direct hazard   = direct_rate   x number of contacts with infectious pigs today
     indirect hazard = indirect_rate x contamination of its pen x (1 - biosecurity)
  3. Disease states are updated:  S -> E -> I -> R (recovered) or D (dead) -> X (carcass removed)
  4. Farm actions happen: isolating detected sick pigs, removing carcasses,
     moving pigs between pens.
  5. Pen contamination is updated and the day's numbers are recorded.

This file has no user-interface code. The Streamlit pages and the tests import it.
"""

import math
import random
from dataclasses import dataclass, field, asdict

# ----------------------------------------------------------------------------
# Disease states
# ----------------------------------------------------------------------------
S = "S"  # Susceptible: healthy, can be infected
E = "E"  # Exposed: infected, not yet able to infect others
I = "I"  # Infectious: sick and spreading the virus
R = "R"  # Recovered: survived the disease (assumed not infectious anymore)
D = "D"  # Dead: died of ASF, carcass still in the pen (still contaminates it)
X = "X"  # Removed: carcass taken out of the farm

STATE_NAMES = {
    S: "Susceptible",
    E: "Exposed",
    I: "Infectious",
    R: "Recovered",
    D: "Dead (carcass in pen)",
    X: "Removed (carcass disposed)",
}

# The only allowed state changes (checked by the tests).
ALLOWED_TRANSITIONS = {
    S: {E},
    E: {I},
    I: {R, D},
    D: {X},
    R: set(),
    X: set(),
}

# ----------------------------------------------------------------------------
# Farm layout (metres). Pens sit in two rows on either side of a corridor.
# ----------------------------------------------------------------------------
PEN_WIDTH = 8.0
PEN_DEPTH = 6.0
CORRIDOR = 3.0
MARGIN = 0.4  # pigs keep this distance from the fence

STEPS_PER_DAY = 6  # movement steps per day (one every 4 hours)
CONTACT_DISTANCE = 1.0  # metres: closer than this counts as a close contact
CONTAMINATION_DECAY = 0.2  # share of pen contamination that disappears per day
WORKER_CARRYOVER = 0.1  # share of other pens' contamination carried in by workers per day
SICK_SPEED_FACTOR = 0.5  # infectious pigs move at half speed


@dataclass
class Settings:
    """All inputs of one simulation run (the values shown in the app's sidebar)."""

    num_pigs: int = 120
    num_pens: int = 6
    initial_infected: int = 2
    days: int = 60
    seed: int = 42

    direct_rate: float = 0.08  # infection hazard per close contact with an infectious pig
    indirect_on: bool = True  # indirect transmission through contaminated pens and workers
    indirect_rate: float = 0.01  # infection hazard per unit of pen contamination per day
    recovery_prob: float = 0.05  # chance an infectious pig recovers instead of dying
    movement_speed: float = 1.0  # metres per hour that pigs walk inside the pen
    transfers_per_week: float = 2.0  # pigs moved by workers from one pen to another

    biosecurity: float = 0.0  # 0..0.9, reduces indirect transmission and worker carry-over
    isolation_on: bool = False  # detected sick pigs are moved to the isolation pen
    detection_delay: int = 2  # days a pig is infectious before it is noticed
    carcass_removal_delay: int = 3  # days a dead pig stays in the pen

    latent_days: tuple = (3, 6)  # min/max days in Exposed
    infectious_days: tuple = (5, 9)  # min/max days in Infectious


@dataclass
class Pig:
    id: int
    pen: int
    x: float
    z: float
    tx: float  # target point the pig walks to
    tz: float
    state: str = S
    day_infected: int = -1
    day_infectious: int = -1
    day_dead: int = -1
    latent_len: int = 0
    infectious_len: int = 0
    isolated: bool = False
    route: str = ""  # how it was infected: initial / direct / indirect


@dataclass
class Result:
    settings: dict
    pens: list  # pen rectangles for drawing
    isolation_pen: dict
    daily: list  # one dict of counts per day
    frames: list  # frames[day][step] = flat list [x0, z0, x1, z1, ...]
    states: list  # states[day] = string with one letter per pig
    infections: list = field(default_factory=list)  # (day, pig id, route)
    summary: dict = field(default_factory=dict)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def pen_rectangles(num_pens):
    """Returns the rectangle (min_x, max_x, min_z, max_z) of every pen and of the isolation pen."""
    cols = math.ceil(num_pens / 2)
    total_width = cols * PEN_WIDTH
    pens = []
    for p in range(num_pens):
        row = 0 if p < cols else 1
        col = p if row == 0 else p - cols
        min_x = -total_width / 2 + col * PEN_WIDTH
        if row == 0:
            min_z, max_z = -CORRIDOR / 2 - PEN_DEPTH, -CORRIDOR / 2
        else:
            min_z, max_z = CORRIDOR / 2, CORRIDOR / 2 + PEN_DEPTH
        pens.append({"min_x": min_x, "max_x": min_x + PEN_WIDTH, "min_z": min_z, "max_z": max_z, "label": f"Pen {p + 1}"})
    iso_x = total_width / 2 + 3.0
    isolation = {"min_x": iso_x, "max_x": iso_x + 6.0, "min_z": -3.0, "max_z": 3.0, "label": "Isolation"}
    return pens, isolation


def random_point(rect, rng):
    return (
        rng.uniform(rect["min_x"] + MARGIN, rect["max_x"] - MARGIN),
        rng.uniform(rect["min_z"] + MARGIN, rect["max_z"] - MARGIN),
    )


def infection_probability(hazard):
    """P = 1 - exp(-hazard). Always between 0 and 1."""
    if hazard <= 0 or math.isnan(hazard):
        return 0.0
    return 1.0 - math.exp(-hazard)


# ----------------------------------------------------------------------------
# The simulation
# ----------------------------------------------------------------------------
class Simulation:
    def __init__(self, settings: Settings):
        self.s = settings
        self.rng = random.Random(settings.seed)  # all randomness comes from this seeded generator
        self.day = 0
        self.pens, self.isolation_pen = pen_rectangles(settings.num_pens)
        self.contamination = [0.0] * settings.num_pens

        # Create the pigs: pig i goes to pen (i mod number of pens).
        self.pigs = []
        for i in range(settings.num_pigs):
            pen = i % settings.num_pens
            x, z = random_point(self.pens[pen], self.rng)
            tx, tz = random_point(self.pens[pen], self.rng)
            self.pigs.append(Pig(i, pen, x, z, tx, tz))

        # Introduce ASF: the first pigs of Pen 1 start as Exposed.
        pen1 = [p for p in self.pigs if p.pen == 0]
        for pig in pen1[: settings.initial_infected]:
            self.infect(pig, "initial")

        self.daily = []
        self.frames = [[self.positions()]]
        self.states = [self.state_string()]
        self.infections = [(0, p.id, "initial") for p in self.pigs if p.route == "initial"]
        self.record(new_infections=len(self.infections), new_direct=0, new_indirect=0)

    # ---- state changes -------------------------------------------------------
    def infect(self, pig, route):
        """S -> E. The pig's latent and infectious period lengths are drawn now."""
        pig.state = E
        pig.day_infected = self.day
        pig.route = route
        pig.latent_len = self.rng.randint(*self.s.latent_days)
        pig.infectious_len = self.rng.randint(*self.s.infectious_days)

    def progress(self, pig):
        """Time-driven changes: E -> I, I -> R or D, D -> X."""
        if pig.state == E and self.day - pig.day_infected >= pig.latent_len:
            pig.state = I
            pig.day_infectious = self.day
        elif pig.state == I and self.day - pig.day_infectious >= pig.infectious_len:
            if self.rng.random() < self.s.recovery_prob:
                pig.state = R
            else:
                pig.state = D
                pig.day_dead = self.day
        elif pig.state == D and self.day - pig.day_dead >= self.s.carcass_removal_delay:
            pig.state = X

    # ---- movement ------------------------------------------------------------
    def area_of(self, pig):
        return self.isolation_pen if pig.isolated else self.pens[pig.pen]

    def move_pigs(self):
        """Every living pig walks toward its target point; at the target it picks a new one."""
        hours = 24 / STEPS_PER_DAY
        for pig in self.pigs:
            if pig.state in (D, X):
                continue  # dead or removed pigs do not move
            speed = self.s.movement_speed * (SICK_SPEED_FACTOR if pig.state == I else 1.0)
            distance = speed * hours
            dx, dz = pig.tx - pig.x, pig.tz - pig.z
            gap = math.hypot(dx, dz)
            if gap <= distance:
                pig.x, pig.z = pig.tx, pig.tz
                pig.tx, pig.tz = random_point(self.area_of(pig), self.rng)
            else:
                pig.x += dx / gap * distance
                pig.z += dz / gap * distance
            # Safety: keep the pig inside its pen (it can never walk through a fence).
            area = self.area_of(pig)
            pig.x = min(max(pig.x, area["min_x"] + MARGIN), area["max_x"] - MARGIN)
            pig.z = min(max(pig.z, area["min_z"] + MARGIN), area["max_z"] - MARGIN)

    def count_contacts(self, contacts):
        """Adds 1 to a susceptible pig's contact count for every infectious pen-mate within 1 m."""
        for pen in range(self.s.num_pens):
            sick = [p for p in self.pigs if p.pen == pen and p.state == I and not p.isolated]
            if not sick:
                continue
            for pig in self.pigs:
                if pig.pen != pen or pig.state != S or pig.isolated:
                    continue
                for other in sick:
                    if math.hypot(pig.x - other.x, pig.z - other.z) <= CONTACT_DISTANCE:
                        contacts[pig.id] = contacts.get(pig.id, 0) + 1

    # ---- one simulated day ---------------------------------------------------
    def step(self):
        self.day += 1
        s = self.s

        # 1. Movement and close contacts
        contacts = {}
        day_frames = []
        for _ in range(STEPS_PER_DAY):
            self.move_pigs()
            self.count_contacts(contacts)
            day_frames.append(self.positions())

        # 2. Infection probabilities (computed for everyone first, applied afterwards)
        new_cases = []
        for pig in self.pigs:
            if pig.state != S:
                continue
            direct = s.direct_rate * contacts.get(pig.id, 0)
            indirect = 0.0
            if s.indirect_on:
                indirect = s.indirect_rate * self.contamination[pig.pen] * (1 - s.biosecurity)
            p = infection_probability(direct + indirect)
            if self.rng.random() < p:
                # Which route caused it? Chosen in proportion to the two hazards.
                route = "direct" if self.rng.random() * (direct + indirect) < direct else "indirect"
                new_cases.append((pig, route))

        # 3. Disease progression, then the new infections
        for pig in self.pigs:
            self.progress(pig)
        for pig, route in new_cases:
            self.infect(pig, route)
            self.infections.append((self.day, pig.id, route))

        # 4. Farm actions
        if s.isolation_on:
            for pig in self.pigs:
                if pig.state == I and not pig.isolated and self.day - pig.day_infectious >= s.detection_delay:
                    pig.isolated = True
                    pig.x, pig.z = random_point(self.isolation_pen, self.rng)
                    pig.tx, pig.tz = random_point(self.isolation_pen, self.rng)
        self.transfer_pigs()

        # 5. Pen contamination: sick pigs and carcasses add to it, part of it fades away,
        #    and workers carry some of the other pens' contamination in.
        sources = [0] * s.num_pens
        for pig in self.pigs:
            if pig.state in (I, D) and not pig.isolated:
                sources[pig.pen] += 1
        old = self.contamination[:]
        for pen in range(s.num_pens):
            others = [old[q] for q in range(s.num_pens) if q != pen]
            carried = WORKER_CARRYOVER * (1 - s.biosecurity) * (sum(others) / len(others) if others else 0)
            self.contamination[pen] = old[pen] * (1 - CONTAMINATION_DECAY) + sources[pen] + carried

        # 6. Record the day
        day_frames[-1] = self.positions()  # include end-of-day moves (isolation, transfers)
        self.frames.append(day_frames)
        self.states.append(self.state_string())
        n_direct = sum(1 for _, r in new_cases if r == "direct")
        self.record(len(new_cases), n_direct, len(new_cases) - n_direct)

    def transfer_pigs(self):
        """Workers move healthy-looking pigs between pens (about transfers_per_week per week)."""
        if self.s.num_pens < 2 or self.s.transfers_per_week <= 0:
            return
        expected = self.s.transfers_per_week / 7
        count = int(expected) + (1 if self.rng.random() < expected - int(expected) else 0)
        for _ in range(count):
            movable = [p for p in self.pigs if p.state in (S, E, I, R) and not p.isolated]
            if not movable:
                return
            pig = self.rng.choice(movable)
            new_pen = self.rng.choice([q for q in range(self.s.num_pens) if q != pig.pen])
            pig.pen = new_pen
            pig.x, pig.z = random_point(self.pens[new_pen], self.rng)
            pig.tx, pig.tz = random_point(self.pens[new_pen], self.rng)

    # ---- recording -----------------------------------------------------------
    def positions(self):
        out = []
        for p in self.pigs:
            out.extend((round(p.x, 2), round(p.z, 2)))
        return out

    def state_string(self):
        # lower-case letter = pig is in the isolation pen
        return "".join(p.state.lower() if p.isolated else p.state for p in self.pigs)

    def record(self, new_infections, new_direct, new_indirect):
        counts = {st: 0 for st in (S, E, I, R, D, X)}
        for p in self.pigs:
            counts[p.state] += 1
        self.daily.append(
            {
                "day": self.day,
                **counts,
                "isolated": sum(1 for p in self.pigs if p.isolated and p.state in (E, I, R)),
                "new_infections": new_infections,
                "new_direct": new_direct,
                "new_indirect": new_indirect,
                "total_infected": sum(1 for p in self.pigs if p.day_infected >= 0),
                "total_dead": counts[D] + counts[X],
            }
        )

    def summary(self):
        """Performance indicators of the finished run."""
        n = self.s.num_pigs
        total_infected = sum(1 for p in self.pigs if p.day_infected >= 0)
        peak = max(self.daily, key=lambda d: d[I])
        return {
            "total_infected": total_infected,
            "percent_infected": 100 * total_infected / n,
            "total_deaths": self.daily[-1]["total_dead"],
            "total_recovered": self.daily[-1][R],
            "peak_infectious": peak[I],
            "peak_day": peak["day"],
            "outbreak_duration": sum(1 for d in self.daily[1:] if d[E] + d[I] > 0),
            "final_susceptible": self.daily[-1][S],
            "direct_infections": sum(1 for _, _, r in self.infections if r == "direct"),
            "indirect_infections": sum(1 for _, _, r in self.infections if r == "indirect"),
        }

    def run(self):
        while self.day < self.s.days:
            self.step()
        return Result(
            settings=asdict(self.s),
            pens=self.pens,
            isolation_pen=self.isolation_pen,
            daily=self.daily,
            frames=self.frames,
            states=self.states,
            infections=self.infections,
            summary=self.summary(),
        )


def run_simulation(settings: Settings) -> Result:
    return Simulation(settings).run()
