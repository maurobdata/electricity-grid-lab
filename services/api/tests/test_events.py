"""Event detection: what the lab notices before anybody asks.

Every detector gets two tests — a case it **must** fire on and a case it must **not**. A
detector that has stopped catching anything looks exactly like a detector with nothing to
catch, and only one of those is a bug.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gridlab.analysis.align import align
from gridlab.analysis.divergence import analyse
from gridlab.analysis.events import (
    carbon_swing,
    cheap_and_clean_disagree,
    import_dependence,
    negative_price,
    rank,
    renewable_surge,
)
from gridlab.domain.models import (
    FlowEdge,
    Flows,
    MixBreakdown,
    MixEntry,
    Price,
    Provenance,
    ScalarObservation,
    Series,
)


def at(hour: float) -> datetime:
    return datetime(2026, 2, 4, tzinfo=UTC) + timedelta(hours=hour)


def series(
    values: dict[float, float], *, provenance: Provenance = Provenance.RECORDED
) -> Series[ScalarObservation]:
    return Series[ScalarObservation](
        zone="DK-DK2",
        points=tuple(
            ScalarObservation(zone="DK-DK2", at=at(h), provenance=provenance, value=v)
            for h, v in sorted(values.items())
        ),
    )


def prices(values: dict[float, float]) -> Series[ScalarObservation]:
    return Series[ScalarObservation](
        zone="DK-DK2",
        points=tuple(
            Price(
                zone="DK-DK2",
                at=at(h),
                provenance=Provenance.RECORDED,
                value=v,
                currency="EUR",
                unit="MWh",
            )
            for h, v in sorted(values.items())
        ),
    )


# --- negative price ---------------------------------------------------------


def test_negative_prices_are_found_and_never_clamped() -> None:
    """The most interesting thing in a price series, and the thing a naive pipeline is most
    likely to treat as an error."""
    findings = negative_price(prices({0: 20, 1: -5, 2: -40, 3: 15}))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "negative_price"
    assert finding.magnitude == -40
    assert finding.at == at(1) and finding.until == at(2)
    assert "-40" in finding.headline
    assert finding.unit == "EUR/MWh"


def test_a_positive_price_series_produces_nothing() -> None:
    assert negative_price(prices({0: 20, 1: 5, 2: 40})) == []


def test_separate_negative_runs_are_separate_findings() -> None:
    """Two hours below zero this evening and two tomorrow morning are two events, not one
    twelve-hour one."""
    findings = negative_price(prices({0: -5, 1: -6, 5: 40, 9: -8, 10: -9}))
    assert len(findings) == 2
    assert [f.at for f in findings] == [at(0), at(9)]


def test_a_deeper_price_outranks_a_longer_one() -> None:
    """One hour at -400 is a bigger story than six at -2."""
    deep = negative_price(prices({0: -400, 1: 10}))[0]
    shallow = negative_price(prices({h: -2.0 for h in range(6)}))[0]
    assert deep.significance > shallow.significance


def test_a_fractional_dip_does_not_earn_a_place_in_the_list() -> None:
    """Filtered from the list, never corrected in the data. Four chips for four dips that
    barely cross zero bury the event somebody actually needed to see."""
    assert negative_price(prices({0: 20, 1: -0.4, 2: 15})) == []


def test_filtering_shallow_dips_keeps_the_deep_one_beside_them() -> None:
    findings = negative_price(prices({0: -0.2, 1: 10, 5: -60, 6: 10, 9: -0.3}))
    assert [f.magnitude for f in findings] == [-60]


def test_timestamps_name_the_day_once_the_window_crosses_midnight() -> None:
    """Findings are read side by side. A bare `03:00` next to a `Thu 06:00` invites exactly
    the wrong inference about which comes first."""
    findings = negative_price(prices({0: -5, 20: 10, 30: -20}))
    assert all(any(day in f.headline for day in ("Wed", "Thu", "Fri")) for f in findings), (
        "a window crossing midnight still reported bare clock times"
    )


def test_timestamps_stay_bare_within_one_calendar_day() -> None:
    """Where there is only one 03:00, a weekday is noise."""
    findings = negative_price(prices({0: 20, 1: -5, 2: -40, 3: 15}))
    assert "from 01:00" in findings[0].headline


def test_a_negative_price_finding_points_the_ui_at_the_window() -> None:
    """The finding is navigation, not just an observation."""
    intent = negative_price(prices({0: 20, 1: -5, 2: -40, 3: 15}))[0].intent
    assert intent is not None
    assert intent.kind == "highlight_window"
    assert intent.signal == "price"
    assert intent.at == at(1) and intent.until == at(2)
    assert intent.reason


# --- carbon swing -----------------------------------------------------------


def test_a_large_carbon_swing_is_reported_as_a_ratio() -> None:
    """A ratio so it means the same in a zone running at 30 and one running at 600."""
    findings = carbon_swing(series({0: 100, 1: 200, 2: 400}))
    assert len(findings) == 1
    assert findings[0].magnitude == 4.0
    assert "4.0x" in findings[0].headline


def test_a_flat_carbon_forecast_is_not_an_event() -> None:
    assert carbon_swing(series({0: 200, 1: 205, 2: 210})) == []


def test_a_carbon_finding_says_it_is_a_forecast() -> None:
    """The provenance rule in prose: a forecast presented as an observation is exactly the
    failure the whole system exists to prevent."""
    finding = carbon_swing(series({0: 100, 1: 200, 2: 400}))[0]
    assert "forecast, not an outcome" in finding.detail


# --- renewable surge --------------------------------------------------------


def test_a_renewable_surge_is_found() -> None:
    findings = renewable_surge(series({0: 20, 1: 35, 2: 75}))
    assert len(findings) == 1
    assert findings[0].magnitude == 55.0


def test_a_small_renewable_rise_is_not_a_surge() -> None:
    assert renewable_surge(series({0: 40, 1: 45, 2: 50})) == []


def test_a_surge_must_rise_rather_than_fall() -> None:
    """Highest-then-lowest is a collapse. Reporting it as a surge would invert the story."""
    assert renewable_surge(series({0: 80, 1: 40, 2: 15})) == []


# --- import dependence ------------------------------------------------------


def mix(entries: dict[str, float], *, flow_traced: bool) -> MixBreakdown:
    total = sum(entries.values())
    return MixBreakdown(
        zone="DK-DK2",
        at=at(0),
        provenance=Provenance.RECORDED,
        flow_traced=flow_traced,
        total_mw=total,
        entries=tuple(
            MixEntry(source=s, power_mw=v, percent=v / total * 100) for s, v in entries.items()
        ),
    )


def flows(edges: dict[str, float]) -> Flows:
    return Flows(
        zone="DK-DK2",
        at=at(0),
        provenance=Provenance.RECORDED,
        edges=tuple(FlowEdge(counterpart_zone=z, net_flow_mw=v) for z, v in edges.items()),
    )


def test_a_zone_running_on_imported_coal_is_reported() -> None:
    """The finding only flow-tracing can support: this zone generates almost no coal and
    consumes a great deal of it."""
    findings = import_dependence(
        production=mix({"wind": 800, "gas": 200}, flow_traced=False),
        consumption=mix({"wind": 500, "gas": 150, "coal": 350}, flow_traced=True),
        flows=flows({"DE": -400, "SE-SE4": -50}),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "import_dependence"
    assert "coal" in finding.headline
    assert "DE" in finding.headline, "the largest trading partner was not named"


def test_a_self_sufficient_zone_produces_no_import_finding() -> None:
    breakdown = {"wind": 900, "gas": 100}
    assert (
        import_dependence(
            production=mix(breakdown, flow_traced=False),
            consumption=mix(breakdown, flow_traced=True),
            flows=flows({"DE": 10, "SE-SE4": -5}),
        )
        == []
    )


def test_the_import_finding_distinguishes_the_two_mixes() -> None:
    """Conflating production and consumption is the most common mistake made with this
    data, so the finding has to name which is which."""
    finding = import_dependence(
        production=mix({"wind": 800, "gas": 200}, flow_traced=False),
        consumption=mix({"wind": 500, "gas": 150, "coal": 350}, flow_traced=True),
        flows=flows({"DE": -400}),
    )[0]
    assert "flow-traced" in finding.detail.lower()
    assert "different questions" in finding.detail


def test_the_import_finding_takes_the_weakest_provenance_of_three_inputs() -> None:
    synthetic = MixBreakdown(
        zone="DK-DK2",
        at=at(0),
        provenance=Provenance.SYNTHETIC,
        flow_traced=True,
        total_mw=1000,
        entries=(MixEntry(source="coal", power_mw=1000, percent=100.0),),
    )
    finding = import_dependence(
        production=mix({"wind": 800, "gas": 200}, flow_traced=False),
        consumption=synthetic,
        flows=flows({"DE": -400}),
    )[0]
    assert finding.derived.provenance is Provenance.SYNTHETIC


# --- the disagreement -------------------------------------------------------


def divergence(carbon: dict[float, float], price: dict[float, float]):  # type: ignore[no-untyped-def]
    aligned = align(series(carbon), prices(price), a_signal="carbon_intensity", b_signal="price")
    assert aligned is not None
    return analyse(aligned, window_periods=3), aligned


def test_cheap_and_clean_being_different_hours_is_a_finding() -> None:
    result, aligned = divergence(
        carbon={0: 400, 1: 400, 2: 400, 3: 100, 4: 100, 5: 100},
        price={0: 10, 1: 10, 2: 10, 3: 200, 4: 200, 5: 200},
    )
    findings = cheap_and_clean_disagree(result, aligned)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.magnitude == 3.0
    assert "hours apart" in finding.headline
    labels = {e.label for e in finding.evidence}
    assert "cheapest window carbon" in labels
    assert "cleanest window price" in labels


def test_a_zone_where_the_two_agree_produces_no_finding() -> None:
    """Agreement is a real answer, not a detector failure — and reporting a disagreement
    that is not there would be the more damaging error."""
    result, aligned = divergence(
        carbon={0: 400, 1: 400, 2: 400, 3: 100, 4: 100, 5: 100},
        price={0: 200, 1: 200, 2: 200, 3: 10, 4: 10, 5: 10},
    )
    assert cheap_and_clean_disagree(result, aligned) == []


def test_the_disagreement_finding_refuses_to_recommend() -> None:
    """It quantifies the trade and stops. What the trade is worth involves values this
    module does not have."""
    result, aligned = divergence(
        carbon={0: 400, 1: 400, 2: 400, 3: 100, 4: 100, 5: 100},
        price={0: 10, 1: 10, 2: 10, 3: 200, 4: 200, 5: 200},
    )
    finding = cheap_and_clean_disagree(result, aligned)[0]
    assert "not a question this lab answers" in finding.detail


def test_the_disagreement_finding_carries_the_marginal_caveat() -> None:
    """The objection an energy-literate reader raises. Raising it first is cheaper than
    being caught by it."""
    result, aligned = divergence(
        carbon={0: 400, 1: 400, 2: 400, 3: 100, 4: 100, 5: 100},
        price={0: 10, 1: 10, 2: 10, 3: 200, 4: 200, 5: 200},
    )
    caveats = " ".join(cheap_and_clean_disagree(result, aligned)[0].derived.caveats)
    assert "marginal unit" in caveats
    assert "not a measured" in caveats


# --- identity and ordering --------------------------------------------------


def test_the_same_finding_computed_twice_has_the_same_id() -> None:
    """Narration is cached against this. Unstable ids would mean paying for the same
    explanation on every poll — and showing the same event as new each time."""
    first = negative_price(prices({0: 20, 1: -5, 2: -40}))[0]
    second = negative_price(prices({0: 20, 1: -5, 2: -40}))[0]
    assert first.id == second.id


def test_different_findings_have_different_ids() -> None:
    a = negative_price(prices({0: -5, 1: -6}))[0]
    b = negative_price(prices({0: -5, 1: -6, 2: -7}))[0]
    assert a.id != b.id


def test_ranking_puts_the_most_significant_first() -> None:
    findings = negative_price(prices({0: -2, 1: 10, 5: -300, 6: 10}))
    ordered = rank(findings)
    assert ordered[0].magnitude == -300


def test_every_finding_carries_provenance() -> None:
    """The rule that does not stop applying because arithmetic happened."""
    findings = [
        *negative_price(prices({0: -5, 1: -6})),
        *carbon_swing(series({0: 100, 1: 200, 2: 400}, provenance=Provenance.SYNTHETIC)),
    ]
    assert len(findings) == 2
    assert findings[0].derived.provenance is Provenance.RECORDED
    assert findings[1].derived.provenance is Provenance.SYNTHETIC
