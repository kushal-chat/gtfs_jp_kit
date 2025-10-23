# Run via uv run --no-project marimo run notebooks/examples.py in base.

import marimo

__generated_with = "0.17.0"
app = marimo.App(width="medium")

@app.cell
def _():
    import pathlib as pl
    import json

    import marimo as mo
    import pandas as pd
    import numpy as np
    import geopandas as gp
    import matplotlib
    import folium as fl

    import gtfs_jp_kit as gkjp

    DATA = pl.Path("japan_data")
    return DATA, fl, gkjp, gp, mo, pd

@app.cell
def _(DATA, gkjp):
    # List feed
    gkjp.list_feed(DATA / "hakodate_shiden.zip")

@app.cell
def _(DATA, gkjp):
    # Read feed and describe
    feed = gkjp.read_feed(DATA / "keifuku_rosen.zip", dist_units="m")
    feed.describe()
    return (feed,)

@app.cell
def _(feed, mo):
    mo.output.append(feed.stop_times)
    feed_1 = feed.append_dist_to_stop_times()
    mo.output.append(feed_1.stop_times)
    return (feed_1,)

@app.cell
def _(feed_1):
    week = feed_1.get_first_week()
    dates = [week[0], week[6]]
    dates
    return (dates,)



@app.cell
def _(feed_1):
    # Trip stats; reuse these for later speed ups
    trip_stats = feed_1.compute_trip_stats()
    trip_stats
    return


@app.cell
def _(dates, feed_1):
    # Pass in trip stats to avoid recomputing them

    network_stats = feed_1.compute_network_stats(dates)
    network_stats
    return


@app.cell
def _(dates, feed_1):
    nts = feed_1.compute_network_time_series(dates, freq="6h")
    nts
    return (nts,)


@app.cell
def _(gkjp, nts):
    gkjp.downsample(nts, freq="12h")
    return


@app.cell
def _(dates, feed, feed_1):
    # Stop time series
    stop_ids = feed.stops.loc[:1, "stop_id"]
    sts = feed_1.compute_stop_time_series(dates, stop_ids=stop_ids, freq="12h")
    sts
    return (sts,)


@app.cell
def _(gkjp, sts):
    gkjp.downsample(sts, freq="d")
    return


@app.cell
def _(dates, feed_1):
    # Route time series

    rts = feed_1.compute_route_time_series(dates, freq="12h")
    rts
    return


@app.cell
def _(dates, feed_1):
    # Route timetable

    route_id = feed_1.routes["route_id"].iat[0]
    feed_1.build_route_timetable(route_id, dates)
    return


@app.cell
def _(dates, feed_1, pd):
    # Locate trips

    rng = pd.date_range("1/1/2000", periods=24, freq="h")
    times = [t.strftime("%H:%M:%S") for t in rng]
    loc = feed_1.locate_trips(dates[0], times)
    loc.head()
    return


@app.cell
def _(feed_1):
    # Map routes

    rsns = feed_1.routes["route_short_name"].iloc[2:4]
    feed_1.map_routes(route_short_names=rsns, show_stops=True)
    
    return


# @app.cell
# def _(feed):
#     # Alternatively map routes without stops using GeoPandas's explore

#     (
#         feed.get_routes(as_gdf=True).explore(
#             column="route_short_name",
#             style_kwds=dict(weight=3),
#             highlight_kwds=dict(weight=8),
#             tiles="CartoDB positron",
#         )
#     )
#     return

if __name__ == "__main__":
    app.run()
