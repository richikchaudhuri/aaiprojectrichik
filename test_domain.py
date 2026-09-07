"""Unit tests for the rule engine. No LLM, no LangGraph - runs on stdlib + pytest."""
import domain
from state import merge_livestock


# ---------------------------------------------------------------- parsing

def test_parses_a_full_test_line():
    r = domain.parse_reading("ammonia 0.5, nitrite 0, nitrate 20, pH 7.4, temp 26")
    assert r["ammonia"] == 0.5
    assert r["nitrite"] == 0.0
    assert r["nitrate"] == 20.0
    assert r["ph"] == 7.4
    assert r["temp_c"] == 26.0


def test_parses_abbreviations_and_separators():
    r = domain.parse_reading("nh3=0.25 no2: 0 no3 = 40 ph is 7.0")
    assert r["ammonia"] == 0.25
    assert r["nitrite"] == 0.0
    assert r["nitrate"] == 40.0
    assert r["ph"] == 7.0


def test_converts_fahrenheit_to_celsius():
    assert domain.parse_reading("temp 78F")["temp_c"] == 25.6
    assert domain.parse_reading("the tank is at 26C")["temp_c"] == 26.0


def test_missing_parameters_stay_none():
    r = domain.parse_reading("ammonia 0.25")
    assert r["ammonia"] == 0.25
    assert r["nitrate"] is None and r["ph"] is None


def test_looks_like_test_result():
    assert domain.looks_like_test_result("ammonia 0.25 nitrite 0")
    assert domain.looks_like_test_result("ph 7.2")
    assert not domain.looks_like_test_result("my neons are gasping at the surface")
    assert not domain.looks_like_test_result("how often should I do water changes?")


# ---------------------------------------------------------------- rules

def test_clean_water_produces_an_ok_alert():
    alerts = domain.evaluate(domain.parse_reading("ammonia 0 nitrite 0 nitrate 20 ph 7.2 temp 25"))
    assert len(alerts) == 1 and alerts[0].startswith("OK")


def test_ammonia_spike_is_critical():
    alerts = domain.evaluate(domain.parse_reading("ammonia 0.5 nitrite 0"))
    assert any(a.startswith("CRITICAL") and "Ammonia" in a for a in alerts)


def test_mild_ammonia_is_high_not_critical():
    alerts = domain.evaluate(domain.parse_reading("ammonia 0.25"))
    assert any(a.startswith("HIGH") for a in alerts)
    assert not any(a.startswith("CRITICAL") for a in alerts)


def test_low_and_high_bounds_both_fire():
    assert any(a.startswith("LOW") for a in domain.evaluate(domain.parse_reading("ph 5.5")))
    assert any(a.startswith("HIGH") for a in domain.evaluate(domain.parse_reading("nitrate 60")))
    assert any(a.startswith("LOW") for a in domain.evaluate(domain.parse_reading("temp 18C")))


def test_cycle_status():
    assert "stage 2" in domain.cycle_status(domain.parse_reading("ammonia 0 nitrite 0.5 nitrate 5"))
    assert "stage 1" in domain.cycle_status(domain.parse_reading("ammonia 1 nitrite 0 nitrate 0"))
    assert "cycled" in domain.cycle_status(
        domain.parse_reading("ammonia 0 nitrite 0 nitrate 20"))


def test_trend_reports_direction():
    readings = [domain.parse_reading("nitrate 10"), domain.parse_reading("nitrate 40")]
    assert "rising" in domain.trend(readings, "nitrate")
    assert domain.trend(readings[:1], "nitrate") is None


# ---------------------------------------------------------------- species

def test_resolve_species_handles_plurals_and_nicknames():
    assert domain.resolve_species("6 neon tetras") == "neon tetra"
    assert domain.resolve_species("some corys") == "corydoras"
    assert domain.resolve_species("a betta") == "betta"
    assert domain.resolve_species("a unicorn fish") is None


def test_parse_additions_handles_multiple_species():
    assert domain.parse_additions("can I add 6 more neon tetras and 3 corys") == {
        "neon tetra": 6, "corydoras": 3}
    assert domain.parse_additions("can I add a betta") == {"betta": 1}


def test_parse_volume():
    assert domain.parse_volume("my tank is 120 litres") == 120
    assert domain.parse_volume("it's a 30 gallon") == 114
    assert domain.parse_volume("no numbers here") is None


# ---------------------------------------------------------------- bioload

def test_bioload_and_capacity():
    assert domain.bioload({"neon tetra": 10}) == 30.0     # 3.0 cm x 1.0 x 10
    assert domain.capacity(110) == 71.5                   # 110 L x 0.65
    assert domain.bioload({}) == 0.0


def test_overstocking_is_rejected():
    v = domain.check_stocking({"goldfish": 2}, "can I add 4 more goldfish", tank_l=150)
    assert not v.ok
    assert any(i.startswith("OVERSTOCKED") for i in v.issues)
    assert v.additions == {}          # rejected additions never reach state


# ---------------------------------------------------------------- compatibility

def test_tiger_barbs_nip_a_betta():
    v = domain.check_stocking({"betta": 1}, "can I add 8 tiger barbs", tank_l=200)
    assert not v.ok
    assert any("FIN NIPPING" in i for i in v.issues)


def test_goldfish_and_tropicals_clash_on_temperature():
    v = domain.check_stocking({"neon tetra": 8}, "can I add 2 goldfish", tank_l=400)
    assert not v.ok
    assert any("TEMPERATURE CLASH" in i for i in v.issues)


def test_schooling_minimum_is_enforced():
    v = domain.check_stocking({}, "can I add 2 neon tetras", tank_l=110)
    assert not v.ok
    assert any("SCHOOL TOO SMALL" in i for i in v.issues)


def test_tank_size_floor_is_enforced():
    v = domain.check_stocking({}, "can I add 1 common pleco", tank_l=110)
    assert not v.ok
    assert any("TANK TOO SMALL" in i for i in v.issues)


def test_a_sensible_addition_is_approved():
    v = domain.check_stocking({"neon tetra": 6}, "can I add 6 corydoras", tank_l=110)
    assert v.ok, v.issues
    assert v.additions == {"corydoras": 6}
    assert v.load_after > v.load_before


def test_near_capacity_is_advice_not_a_rejection():
    v = domain.check_stocking({}, "can I add 20 platies", tank_l=200)
    assert v.ok
    assert any(i.startswith("NEAR CAPACITY") for i in v.issues)
    assert v.additions == {"platy": 20}


def test_unparseable_request_is_not_ok():
    v = domain.check_stocking({}, "can I add something nice")
    assert not v.ok and v.requested == {}


# ---------------------------------------------------------------- reducer

def test_merge_livestock_adds_instead_of_overwriting():
    assert merge_livestock({"neon tetra": 6}, {"neon tetra": 4, "corydoras": 3}) == {
        "neon tetra": 10, "corydoras": 3}


def test_merge_livestock_drops_species_that_reach_zero():
    assert merge_livestock({"guppy": 2}, {"guppy": -2}) == {}


def test_merge_livestock_handles_empty_sides():
    assert merge_livestock({}, {"betta": 1}) == {"betta": 1}
    assert merge_livestock({"betta": 1}, {}) == {"betta": 1}
