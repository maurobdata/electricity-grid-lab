"""The capability matrix must match the documentation, and nothing else may invent a URL.

This is the test that enforces the brief's hardest rule — never invent an Electricity Maps
endpoint. It parses ``docs/electricity-maps-api.md`` and asserts the code agrees with it,
so drift in either direction fails here rather than as a 400 in Copenhagen.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gridlab.emaps.errors import UnsupportedEndpoint
from gridlab.emaps.signals import (
    FORECAST_NEEDS_WINDOW,
    NODE_ADDRESSED,
    PAST_RANGE_MAX_DAYS,
    SUPPORTED,
    BreakdownType,
    Granularity,
    Signal,
    SourceType,
    Temporality,
    path_for,
    supported_horizons,
    supports,
)


def _find_docs() -> Path:
    """Locate the reference doc from inside the container or from a repo checkout."""
    here = Path(__file__).resolve()
    for base in (here.parents[1], *here.parents[2:5]):
        candidate = base / "docs" / "electricity-maps-api.md"
        if candidate.is_file():
            return candidate
    return here.parents[1] / "docs" / "electricity-maps-api.md"


DOCS = _find_docs()


def _signal_table_rows() -> list[list[str]]:
    text = DOCS.read_text(encoding="utf-8")
    table = text.split("## Endpoints", 1)[1].split("Temporalities:", 1)[0]
    rows = []
    for line in table.splitlines():
        if line.startswith("|"):
            rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def documented_signals() -> set[str]:
    """Path segments from the *second column* of the signal table.

    Only that column names an endpoint. The Notes column also contains backticked
    identifiers — the eleven ``electricity-source`` sub-types — and scooping those up would
    make the test demand a Signal enum member for `wind`, which is not a signal.
    """
    found: set[str] = set()
    for cells in _signal_table_rows():
        if len(cells) < 2:
            continue
        for token in re.findall(r"`([a-z0-9-]+(?:/<[a-zA-Z]+>)?)`", cells[1]):
            found.add(token.split("/")[0])
    return found


def documented_source_types() -> set[str]:
    """The ``electricity-source/<sourceType>`` values, from that row's Notes column."""
    for cells in _signal_table_rows():
        if len(cells) >= 3 and "electricity-source" in cells[1]:
            return set(re.findall(r"`([a-z-]+)`", cells[2]))
    return set()


def test_docs_file_exists() -> None:
    assert DOCS.is_file(), (
        f"{DOCS} is missing. The capability matrix is only trustworthy if the document it "
        f"claims to mirror actually exists."
    )


def test_every_code_signal_is_documented() -> None:
    documented = documented_signals()
    undocumented = {s.value for s in Signal} - documented
    assert not undocumented, (
        f"These signals exist in code but not in docs/electricity-maps-api.md: "
        f"{sorted(undocumented)}. Add them to the doc with a source, or delete them."
    )


def test_every_documented_signal_is_in_code() -> None:
    in_code = {s.value for s in Signal}
    missing = documented_signals() - in_code
    assert not missing, (
        f"Documented but not implemented: {sorted(missing)}. Add to the Signal enum and "
        f"to SUPPORTED."
    )


def test_source_types_match_the_documentation() -> None:
    """`electricity-source/<type>` is a path segment, so a typo is a 404 mid-demo."""
    documented = documented_source_types()
    assert documented, "No source types found in the docs table - has the format changed?"
    assert {s.value for s in SourceType} == documented


def test_every_signal_has_a_supported_entry() -> None:
    assert set(SUPPORTED) == set(Signal)


def test_lmp_has_no_forecast() -> None:
    """Documented exception: calling LMP forecast returns HTTP 400.

    Encoding it here means a wrong call fails locally and instantly.
    """
    assert not supports(Signal.LMP_DAY_AHEAD, Temporality.FORECAST)
    with pytest.raises(UnsupportedEndpoint, match="does not offer"):
        path_for(Signal.LMP_DAY_AHEAD, Temporality.FORECAST)


def test_level_signals_reject_history() -> None:
    """The access list advertises level/history, but the API returns 400 for it."""
    for signal in (
        Signal.CARBON_INTENSITY_LEVEL,
        Signal.RENEWABLE_PERCENTAGE_LEVEL,
        Signal.CARBON_FREE_PERCENTAGE_LEVEL,
    ):
        assert Temporality.HISTORY not in SUPPORTED[signal]
        assert Temporality.LATEST in SUPPORTED[signal]


def test_price_has_the_extra_temporalities() -> None:
    """`combined` blends published and modelled prices in one call - unique to this API."""
    assert supports(Signal.PRICE_DAY_AHEAD, Temporality.COMBINED)
    assert supports(Signal.PRICE_DAY_AHEAD, Temporality.ACTUAL)
    assert not supports(Signal.CARBON_INTENSITY, Temporality.COMBINED)


@pytest.mark.parametrize(
    ("signal", "temporality", "expected"),
    [
        (Signal.CARBON_INTENSITY, Temporality.LATEST, "carbon-intensity/latest"),
        (Signal.CARBON_INTENSITY, Temporality.PAST_RANGE, "carbon-intensity/past-range"),
        (Signal.ELECTRICITY_MIX, Temporality.FORECAST, "electricity-mix/forecast"),
        (Signal.PRICE_DAY_AHEAD, Temporality.COMBINED, "price-day-ahead/combined"),
        (Signal.NET_LOAD, Temporality.HISTORY, "net-load/history"),
    ],
)
def test_path_construction(signal: Signal, temporality: Temporality, expected: str) -> None:
    assert path_for(signal, temporality) == expected


def test_electricity_source_needs_a_source_type() -> None:
    assert (
        path_for(Signal.ELECTRICITY_SOURCE, Temporality.LATEST, source_type=SourceType.WIND)
        == "electricity-source/wind/latest"
    )
    with pytest.raises(UnsupportedEndpoint, match="requires a source_type"):
        path_for(Signal.ELECTRICITY_SOURCE, Temporality.LATEST)


def test_source_type_is_rejected_for_other_signals() -> None:
    """Otherwise a typo silently produces carbon-intensity data labelled as wind."""
    with pytest.raises(UnsupportedEndpoint, match="only meaningful"):
        path_for(Signal.CARBON_INTENSITY, Temporality.LATEST, source_type=SourceType.WIND)


def test_forecast_horizons_are_per_signal() -> None:
    """Contradicts the documentation, which says horizons are plan-dependent.

    Swept against the live API: the intensity and percentage signals take 6/24/48/72, while
    mix, flows and the load signals accept only 24 and return 400 for the rest.
    """
    assert supported_horizons(Signal.CARBON_INTENSITY) == (6, 24, 48, 72)
    assert supported_horizons(Signal.ELECTRICITY_MIX) == (24,)
    assert supported_horizons(Signal.NET_LOAD) == (24,)


def test_price_forecast_takes_no_horizon_at_all() -> None:
    """`price-day-ahead/forecast` requires start and end; horizonHours is rejected."""
    assert supported_horizons(Signal.PRICE_DAY_AHEAD) == ()
    assert Signal.PRICE_DAY_AHEAD in FORECAST_NEEDS_WINDOW


def test_lmp_is_addressed_by_node_not_zone() -> None:
    """A zone-only request returns 400 "Missing arguments \\"node\\"", so nothing in this
    lab should treat it as an ordinary zone signal."""
    assert Signal.LMP_DAY_AHEAD in NODE_ADDRESSED


def test_breakdown_type_values_are_the_ones_the_api_accepts() -> None:
    """`production` and `consumption` are rejected. The first version of the matrix used
    exactly those two names and would have 400'd on the first live mix request."""
    assert {b.value for b in BreakdownType} == {"normal", "flow-traced"}


def test_documented_range_caps() -> None:
    """10 days hourly, 100 days daily - stated explicitly in the documentation."""
    assert PAST_RANGE_MAX_DAYS[Granularity.HOURLY] == 10
    assert PAST_RANGE_MAX_DAYS[Granularity.DAILY] == 100


def test_every_granularity_has_a_cap() -> None:
    assert set(PAST_RANGE_MAX_DAYS) == set(Granularity)
