"""
This module defines a Feed class to represent GTFS feeds.
There is an instance attribute for every GTFS table (routes, stops, etc.),
which stores the table as a Pandas DataFrame,
or as ``None`` in case that table is missing.

This module now also allows for SQL functionality, and loading into SQLModels.
This allows for relational representation of data, and crucially validation of GTFS
files, according to publicly released detailed guidelines. It represents a first
step at making it easier to use GTFS data at scale, especially since any file
apart from small lines will likely reach the mid-high 100000 line range for trips over a
span of a week.

SQL also allows for usage with PostGIS, pgNetworks, and more. 
SQLModel allows for connection with FastAPI using Pydantic.

Author: Kushal Chattopadhyay
"""

import pathlib as pl
import shutil
import tempfile
import zipfile
from copy import deepcopy
from typing import Literal, Union, Dict

import pandas as pd
import requests
from sqlmodel import SQLModel

from . import cleaners as cn
from . import constants as cs
from . import helpers as hp

from .sqlmodels import (
    Agency, AgencyJP,
    Stop,
    Route,
    Trip,
    OfficeJP,
    PatternJP,
    StopTime,
    Calendar, CalendarDate,
    FareAttribute, FareRule,
    Shape,
    Frequency,
    Transfer,
    FeedInfo,
    Translation,
    TABLE_MAP
)


class Feed(object):
    """
    An instance of this class represents a not-necessarily-valid GTFS feed,
    where GTFS tables are stored as DataFrames.
    Beware that the stop times DataFrame can be big (several gigabytes),
    so make sure you have enough memory to handle it.

    There are also a few secondary instance attributes that are derived
    from the primary attributes and are automatically updated when the
    primary attributes change.
    However, for this update to work, you must update the primary
    attributes like this (good)::

        feed.trips['route_short_name'] = 'bingo'
        feed.trips = feed.trips

    and **not** like this (bad)::

        feed.trips['route_short_name'] = 'bingo'

    The first way ensures that the altered trips DataFrame is saved as
    the new ``trips`` attribute, but the second way does not.

    """

    # Import heaps of methods from modules split by functionality;
    # i learned this trick from
    # https://groups.google.com/d/msg/comp.lang.python/goLBrqcozNY/DPgyaZ6gAwAJ
    from .calendar import get_dates, get_first_week, get_week, subset_dates
    from .cleaners import (
        aggregate_routes,
        aggregate_stops,
        clean,
        clean_ids,
        clean_route_short_names,
        clean_times,
        drop_invalid_columns,
        drop_zombies,
        extend_id,
    )
    from .miscellany import (
        assess_quality,
        compute_bounds,
        compute_centroid,
        compute_convex_hull,
        compute_network_stats,
        compute_network_time_series,
        compute_screen_line_counts,
        convert_dist,
        create_shapes,
        describe,
        list_fields,
        restrict_to_agencies,
        restrict_to_area,
        restrict_to_dates,
        restrict_to_routes,
        restrict_to_trips,
    )
    from .routes import (
        build_route_timetable,
        compute_route_stats,
        compute_route_time_series,
        get_routes,
        map_routes,
        routes_to_geojson,
    )
    from .shapes import (
        append_dist_to_shapes,
        build_geometry_by_shape,
        geometrize_shapes,
        get_shapes,
        get_shapes_intersecting_geometry,
        shapes_to_geojson,
        split_simple,
    )
    from .stop_times import (
        append_dist_to_stop_times,
        get_start_and_end_times,
        get_stop_times,
        stop_times_to_geojson,
    )
    from .stops import (
        build_geometry_by_stop,
        build_stop_timetable,
        compute_stop_activity,
        compute_stop_stats,
        compute_stop_time_series,
        geometrize_stops,
        get_stops,
        get_stops_in_area,
        map_stops,
        stops_to_geojson,
        ungeometrize_stops,
    )
    from .trips import (
        compute_busiest_date,
        compute_trip_activity,
        compute_trip_stats,
        get_active_services,
        get_trips,
        locate_trips,
        map_trips,
        name_stop_patterns,
        trips_to_geojson,
    )

    def __init__(
        self,
        dist_units: str,
        agency: pd.DataFrame | None = None,              # 2-1. agency.txt
        agency_jp: pd.DataFrame | None = None,           # 2-1. agency_jp.txt
        stops: pd.DataFrame | None = None,               # 2-2. stops.txt
        routes: pd.DataFrame | None = None,              # 2-3. routes.txt
        trips: pd.DataFrame | None = None,               # 2-4. trips.txt
        office_jp: pd.DataFrame | None = None,           # 2-5. office_jp.txt
        pattern_jp: pd.DataFrame | None = None,          # 2-6. pattern_jp.txt
        stop_times: pd.DataFrame | None = None,          # 2-7. stop_times.txt
        calendar: pd.DataFrame | None = None,            # 2-8. calendar.txt
        calendar_dates: pd.DataFrame | None = None,      # 2-8. calendar_dates.txt
        fare_attributes: pd.DataFrame | None = None,     # 2-9. fare_attributes.txt
        fare_rules: pd.DataFrame | None = None,          # 2-9. fare_rules.txt
        shapes: pd.DataFrame | None = None,              # 2-10. shapes.txt
        frequencies: pd.DataFrame | None = None,         # 2-11. frequencies.txt
        transfers: pd.DataFrame | None = None,           # 2-12. transfers.txt
        feed_info: pd.DataFrame | None = None,           # 2-13. feed_info.txt
        translations: pd.DataFrame | None = None,        # 2-14. translations.txt
    ):
        """
        Modified for GTFS-JP.
        https://www.mlit.go.jp/sogoseisaku/transport/content/001419163.pdf

        Assume that every non-None input is a DataFrame,
        except for ``dist_units`` which should be a string in
        :const:`.constants.DIST_UNITS`.

        No other format checking is performed.
        In particular, a Feed instance need not represent a valid GTFS
        feed.
        """
        # Set primary attributes from inputs.
        # The @property magic below will then
        # validate some and set some derived attributes
        for prop, val in locals().items():
            if prop in cs.FEED_ATTRS:
                setattr(self, prop, val)

    @property
    def dist_units(self):
        """
        The distance units of the Feed.
        """
        return self._dist_units

    @dist_units.setter
    def dist_units(self, val):
        if val not in cs.DIST_UNITS:
            raise ValueError(
                f"Distance units are required and must lie in {cs.DIST_UNITS}"
            )
        else:
            self._dist_units = val

    def __str__(self):
        """
        Print the first five rows of each GTFS table.
        """
        d = {}
        for table in cs.DTYPES:
            try:
                d[table] = getattr(self, table).head(5)
            except Exception:
                d[table] = None
        d["dist_units"] = self.dist_units

        return "\n".join([f"* {k} --------------------\n\t{v}" for k, v in d.items()])

    def __eq__(self, other):
        """
        Define two feeds be equal if and only if their
        :const:`.constants.FEED_ATTRS` attributes are equal,
        or almost equal in the case of DataFrames
        (but not groupby DataFrames).
        Almost equality is checked via :func:`.helpers.almost_equal`,
        which   canonically sorts DataFrame rows and columns.
        """
        # Return False if failures
        for key in cs.FEED_ATTRS:
            x = getattr(self, key)
            y = getattr(other, key)
            # DataFrame case
            if isinstance(x, pd.DataFrame):
                if not isinstance(y, pd.DataFrame) or not hp.almost_equal(x, y):
                    return False
            # Other case
            else:
                if x != y:
                    return False
        # No failures
        return True

    def copy(self) -> "Feed":
        """
        Return a copy of this feed, that is, a feed with all the same
        attributes.
        """
        other = Feed(dist_units=self.dist_units)
        for key in set(cs.FEED_ATTRS) - set(["dist_units"]):
            value = getattr(self, key)
            if isinstance(value, pd.DataFrame):
                # Pandas copy DataFrame
                value = value.copy()
            setattr(other, key, value)

        return other

    def to_file(self, path: pl.Path, ndigits: int | None = None) -> None:
        """
        Write this Feed to the given path.
        If the path ends in '.zip', then write the feed as a zip archive.
        Otherwise assume the path is a directory, and write the feed as a
        collection of CSV files to that directory, creating the directory
        if it does not exist.
        Round all decimals to ``ndigits`` decimal places, if given.
        All distances will be the distance units ``feed.dist_units``.
        By the way, 6 decimal degrees of latitude and longitude is enough to locate
        an individual cat.
        """
        path = pl.Path(path)

        if path.suffix == ".zip":
            # Write to temporary directory before zipping
            zipped = True
            tmp_dir = tempfile.TemporaryDirectory()
            new_path = pl.Path(tmp_dir.name)
        else:
            zipped = False
            if not path.exists():
                path.mkdir()
            new_path = path

        for table in cs.DTYPES:
            f = getattr(self, table)
            if f is not None:
                p = new_path / (table + ".txt")
                if ndigits is not None:
                    f.to_csv(p, index=False, float_format=f"%.{ndigits}f")
                else:
                    f.to_csv(p, index=False)

        # Zip directory
        if zipped:
            basename = str(path.parent / path.stem)
            shutil.make_archive(basename, format="zip", root_dir=tmp_dir.name)
            tmp_dir.cleanup()

# -------------------------------------
# Update: Load into Pydantic / SQLModel
# -------------------------------------
def _load_feed_in_sql_format(feed_dict: Dict[str, pd.DataFrame], dist_units: str) -> Dict[str, SQLModel]:
    """
    Convert GTFS feed DataFrames into SQLModel instances based on TABLE_MAP.
    Returns a dict mapping table names to lists of SQLModel instances.

    Args:
      feed_dict: Dict[str, pd.DataFrame], dictionary over all GTFS JP files in zip
      dist_units: str

    Returns:
      sql_models: Dict[str, SQLModel]
    """

    sql_models: dict[str, list] = {}

    for table_name, df in feed_dict.items():
        # Skip non-table attributes like dist_units
        if table_name == "dist_units" or df is None:
            continue

        # Make sure model class exists
        model_class = TABLE_MAP.get(table_name)
        if model_class is None:
            print(f"Skipping unknown table: {table_name}")
            continue

        # Convert DataFrame rows into SQLModel instances
        try:
            # Convert NaNs to None for Pydantic validation
            df = df.where(pd.notnull(df), None)
            sql_models[table_name] = [
                model_class(**row) for row in df.to_dict(orient="records")
            ]
        except Exception as e:
            print(f"Error loading table '{table_name}': {e}")
            sql_models[table_name] = []

    print(f"Loaded {len(sql_models)} SQLModel tables")
    return sql_models

# -------------------------------------
# Functions about input and output
# -------------------------------------
def list_feed(path: pl.Path) -> pd.DataFrame:
    """
    Given a path (string or Path object) to a GTFS zip file or
    directory, record the file names and file sizes of the contents,
    and return the result in a DataFrame with the columns:

    - ``'file_name'``
    - ``'file_size'``
    """
    path = pl.Path(path)
    if not path.exists():
        raise ValueError(f"Path {path} does not exist")

    # Collect rows of DataFrame
    rows = []
    if path.is_file():
        # Zip file
        with zipfile.ZipFile(str(path)) as src:
            for x in src.infolist():
                if x.filename == "./":
                    continue
                d = {}
                d["file_name"] = x.filename
                d["file_size"] = x.file_size
                rows.append(d)
    else:
        # Directory
        for x in path.iterdir():
            d = {}
            d["file_name"] = x.name
            d["file_size"] = x.stat().st_size
            rows.append(d)

    return pd.DataFrame(rows)

def _read_feed_from_path(path: pl.Path, dist_units: str) -> Feed:
    """
    Helper function for :func:`read_feed`.
    Create a Feed instance from the given path and given distance units.
    The path should be a directory containing GTFS text files or a
    zip file that unzips as a collection of GTFS text files
    (and not as a directory containing GTFS text files).
    The distance units given must lie in :const:`constants.dist_units`

    Notes:

    - Ignore non-GTFS files in the feed
    - Automatically strip whitespace from the column names in GTFS files

    """
    path = pl.Path(path)
    if not path.exists():
        raise ValueError(f"Path {path} does not exist")

    # Unzip path to temporary directory if necessary
    if path.is_file():
        zipped = True
        tmp_dir = tempfile.TemporaryDirectory()
        src_path = pl.Path(tmp_dir.name)
        shutil.unpack_archive(str(path), tmp_dir.name, "zip")
    else:
        zipped = False
        src_path = path

    # Read files into feed dictionary of DataFrames
    feed_dict = {table: None for table in cs.DTYPES}
    for p in src_path.iterdir():
        table = p.stem
        # Skip empty files, irrelevant files, and files with no data
        if (
            p.is_file()
            and p.stat().st_size
            and p.suffix == ".txt"
            and table in feed_dict
        ):
            # utf-8-sig gets rid of the byte order mark (BOM);
            # see http://stackoverflow.com/questions/17912307/u-ufeff-in-python-string
            csv_options = {
                "na_values": ["", " ", "nan", "NaN", "null"],  # Add space to na_values
                "keep_default_na": True,
                "dtype_backend": "numpy_nullable",  # Use nullable dtypes
            }
            df = pd.read_csv(
                p, dtype=cs.DTYPES[table], encoding="utf-8-sig", **csv_options
            )
            if not df.empty:
                feed_dict[table] = cn.clean_column_names(df)

    feed_dict["dist_units"] = dist_units

    # Delete temporary directory
    if zipped:
        tmp_dir.cleanup()

    sqlmodels = _load_feed_in_sql_format(feed_dict, dist_units=dist_units)
    return sqlmodels
    # return Feed(**feed_dict)

def _read_feed_from_url(url: str, dist_units: str) -> Feed:
    """
    Helper function for :func:`read_feed`.
    Create a Feed instance from the given URL and given distance units.
    Assume the URL is valid and let the Requests library raise any errors.

    Notes:

    - Ignore non-GTFS files in the feed
    - Automatically strip whitespace from the column names in GTFS files

    """
    f = tempfile.NamedTemporaryFile(delete=False)
    with requests.get(url, allow_redirects=True) as r:
        f.write(r._content)
    f.close()
    feed = _read_feed_from_path(f.name, dist_units=dist_units)
    pl.Path(f.name).unlink()

    return feed

def read_feed(path_or_url: pl.Path | str, dist_units: str) -> Feed:
    """
    Create a Feed instance from the given path or URL and given distance units.
    If the path exists, then call :func:`_read_feed_from_path`.
    Else if the URL has OK status according to Requests, then call
    :func:`_read_feed_from_url`.
    Else raise a ValueError.

    Notes:

    - Ignore non-GTFS files in the feed
    - Automatically strip whitespace from the column names in GTFS files

    Updates: Using SQLModel / Pydantic for easier data usage and open-source development.

    Args:
    - path_or_url: pl.Path

    Returns: 
    - feed: Feed

    If loading into sql, all SQLModel models from ./sqlmodels.py are populated and returned.
    """

    try:
        path_exists = pl.Path(path_or_url).exists()
    except OSError:
        path_exists = False
    if path_exists:
        feed = _read_feed_from_path(path_or_url, dist_units=dist_units)
    else:
        feed = _read_feed_from_url(path_or_url, dist_units=dist_units)

    return feed