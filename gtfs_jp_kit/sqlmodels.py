"""
Allows for easy usage of GTFS-JP, using SQLModel (thus Pydantic) and typing to create SQL-enabled usage.

There are rich relationship, structured output, and data validation information included
in the following specification for transport.
https://www.mlit.go.jp/sogoseisaku/transport/content/001419163.pdf

Use indexing for database efficiency and relationships according to above specification.
"""

from sqlmodel import Field, Relationship, SQLModel, MetaData
from typing import Optional, Literal, List

# 各行の末尾は CRLF 又は LF の改行文字で終わらせ、文字コードは UTF-8 で保存。
import locale
locale.setlocale(locale.LC_ALL, 'ja_JP.UTF-8')

# meta = MetaData(schema="gtfs")

"""
AGENCY
"""

class Agency(SQLModel, table=True):
    agency_id: str = Field(primary_key=True) 
    agency_name: str = Field(index=True) 
    agency_url: str
    agency_timezone: str = Field(default="Asia/Tokyo")
    agency_lang: str = Field(default="ja")
    agency_phone: Optional[str] = None
    agency_fare_url: Optional[str] = None
    agency_email: Optional[str] = None

    # Relationships
    routes: List["Route"] = Relationship(back_populates="agency")
    agency_jp: Optional["AgencyJP"] = Relationship(
        back_populates="agency"
    )

class AgencyJP(SQLModel, table=True):
    __tablename__ = "agency_jp"

    agency_id: str = Field(primary_key=True, foreign_key="agency.agency_id")
    agency_official_name: Optional[str] = Field(default=None, index=True) 
    agency_zip_number: Optional[str] = None
    agency_address: Optional[str] = None
    agency_president_pos: Optional[str] = None
    agency_president_name: Optional[str] = None

    # Relationship
    agency: Agency = Relationship(back_populates="agency_jp")

"""
ROUTES: LAYER 2 
"""

class Route(SQLModel, table=True):
    __tablename__ = "routes"

    route_id: str = Field(primary_key=True) 
    agency_id: str = Field(foreign_key="agency.agency_id")
    route_short_name: str
    route_long_name: str
    route_desc: Optional[str] = None
    route_type: int = 3
    route_url: Optional[str] = None
    route_color: Optional[str] = None
    route_text_color: Optional[str] = None
    jp_parent_route_id: Optional[str] = None

    # Relationships
    agency: Agency = Relationship(back_populates="routes")
    trips: List["Trip"] = Relationship(back_populates="route")
    fare_rules: List["FareRule"] = Relationship(back_populates="route")


"""
TRIPS / FARE RULES: Layer 3
"""

class Trip(SQLModel, table=True):
    __tablename__ = "trips"
    
    trip_id: str = Field(primary_key=True)
    route_id: str = Field(foreign_key="routes.route_id")
    service_id: str = Field(foreign_key="calendar.service_id")
    trip_headsign: Optional[str] = None
    trip_short_name: Optional[str] = None
    direction_id: Optional[int] = None
    block_id: Optional[str] = None
    shape_id: Optional[str] = Field(default=None, foreign_key="shapes.shape_id")
    wheelchair_accessible: Optional[int] = None
    bikes_allowed: Optional[int] = None
    jp_trip_desc: Optional[str] = None
    jp_trip_desc_symbol: Optional[str] = None
    jp_office_id: Optional[str] = Field(default=None, foreign_key="office_jp.office_id")
    jp_pattern_id: Optional[str] = Field(default=None, foreign_key="pattern_jp.jp_pattern_id")

    # Relationships
    route: Route = Relationship(back_populates="trips")
    service: "Calendar" = Relationship(back_populates="trips")
    stop_times: List["StopTime"] = Relationship(back_populates="trip")
    shape: Optional["Shape"] = Relationship(back_populates="trips")
    frequencies: List["Frequency"] = Relationship(back_populates="trip")
    office_jp: Optional["OfficeJP"] = Relationship(back_populates="trips")
    pattern_jp: Optional["PatternJP"] = Relationship(back_populates="trips")


class FareAttribute(SQLModel, table=True):
    __tablename__ = "fare_attributes"
    
    fare_id: str = Field(primary_key=True)
    price: float
    currency_type: str = "JPY"
    payment_method: int
    transfers: int
    transfer_duration: Optional[int] = None

    # Relationships
    fare_rules: List["FareRule"] = Relationship(back_populates="fare_attribute")


class FareRule(SQLModel, table=True):
    __tablename__ = "fare_rules"
    
    fare_id: str = Field(primary_key=True, foreign_key="fare_attributes.fare_id")
    route_id: Optional[str] = Field(default=None, foreign_key="routes.route_id")
    origin_id: str = Field(primary_key=True)
    destination_id: str = Field(primary_key=True)
    contains_id: Optional[str] = None

    # Relationships
    route: Optional[Route] = Relationship(back_populates="fare_rules")
    fare_attribute: FareAttribute = Relationship(back_populates="fare_rules")

"""
CALENDAR
"""

class Calendar(SQLModel, table=True):
    __tablename__ = "calendar"
    
    service_id: str = Field(primary_key=True)
    monday: int
    tuesday: int
    wednesday: int
    thursday: int
    friday: int
    saturday: int
    sunday: int
    start_date: str
    end_date: str

    # Relationships
    trips: List[Trip] = Relationship(back_populates="service")
    calendar_dates: List["CalendarDate"] = Relationship(back_populates="service")


class CalendarDate(SQLModel, table=True):
    __tablename__ = "calendar_dates"
    
    service_id: str = Field(primary_key=True, foreign_key="calendar.service_id")
    date: str = Field(primary_key=True)
    exception_type: int

    # Relationship
    service: Calendar = Relationship(back_populates="calendar_dates")

"""
STOPS
"""

class Stop(SQLModel, table=True):
    __tablename__ = "stops"
    
    stop_id: str = Field(primary_key=True)
    stop_code: Optional[str] = None
    stop_name: str
    stop_desc: Optional[str] = None
    stop_lat: float
    stop_lon: float
    zone_id: str
    stop_url: Optional[str] = None
    location_type: Optional[int] = None
    parent_station: Optional[str] = Field(default=None, foreign_key="stops.stop_id")
    stop_timezone: Optional[str] = None
    wheelchair_boarding: Optional[int] = None

    # Relationships
    stop_times: List["StopTime"] = Relationship(back_populates="stop")
    transfers_from: List["Transfer"] = Relationship(
        back_populates="from_stop",
        sa_relationship_kwargs={"foreign_keys": "Transfer.from_stop_id"}
    )
    transfers_to: List["Transfer"] = Relationship(
        back_populates="to_stop",
        sa_relationship_kwargs={"foreign_keys": "Transfer.to_stop_id"}
    )
    # Self-referential for parent_station
    child_stops: List["Stop"] = Relationship(
        back_populates="parent_stop",
        sa_relationship_kwargs={"foreign_keys": "Stop.parent_station"}
    )
    parent_stop: Optional["Stop"] = Relationship(
        back_populates="child_stops",
        sa_relationship_kwargs={"remote_side": "Stop.stop_id"}
    )


class StopTime(SQLModel, table=True):
    __tablename__ = "stop_times"
    
    trip_id: str = Field(primary_key=True, foreign_key="trips.trip_id")
    stop_id: str = Field(foreign_key="stops.stop_id")
    arrival_time: str
    departure_time: str
    stop_sequence: int = Field(primary_key=True)
    stop_headsign: Optional[str] = None
    pickup_type: Optional[int] = None
    drop_off_type: Optional[int] = None
    shape_dist_traveled: Optional[float] = None
    timepoint: Optional[int] = None

    # Relationships
    trip: Trip = Relationship(back_populates="stop_times")
    stop: Stop = Relationship(back_populates="stop_times")


class Transfer(SQLModel, table=True):
    __tablename__ = "transfers"
    
    from_stop_id: str = Field(primary_key=True, foreign_key="stops.stop_id")
    to_stop_id: str = Field(primary_key=True, foreign_key="stops.stop_id")
    transfer_type: int
    min_transfer_time: Optional[int] = None

    # Relationships
    from_stop: Stop = Relationship(
        back_populates="transfers_from",
        sa_relationship_kwargs={"foreign_keys": "[Transfer.from_stop_id]"}
    )
    to_stop: Stop = Relationship(
        back_populates="transfers_to",
        sa_relationship_kwargs={"foreign_keys": "[Transfer.to_stop_id]"}
    )


"""
SHAPES
"""

class Shape(SQLModel, table=True):
    __tablename__ = "shapes"
    
    shape_id: str = Field(primary_key=True)
    shape_pt_lat: float = Field(primary_key=True)
    shape_pt_lon: float = Field(primary_key=True)
    shape_pt_sequence: int
    shape_dist_traveled: Optional[float] = None

    # Relationships
    trips: List[Trip] = Relationship(back_populates="shape")


"""
FREQUENCIES
"""

class Frequency(SQLModel, table=True):
    __tablename__ = "frequencies"
    
    trip_id: str = Field(primary_key=True, foreign_key="trips.trip_id")
    start_time: str = Field(primary_key=True)
    end_time: str
    headway_secs: int
    exact_times: Optional[int] = None

    # Relationship
    trip: Trip = Relationship(back_populates="frequencies")


"""
JAPAN-SPECIFIC EXTENSIONS
"""

class OfficeJP(SQLModel, table=True):
    __tablename__ = "office_jp"
    
    office_id: str = Field(primary_key=True)
    office_name: str
    office_url: Optional[str] = None
    office_phone: Optional[str] = None

    # Relationships
    trips: List[Trip] = Relationship(back_populates="office_jp")


class PatternJP(SQLModel, table=True):
    __tablename__ = "pattern_jp"
    
    jp_pattern_id: str = Field(primary_key=True)
    route_update_date: Optional[str] = None
    origin_stop: Optional[str] = None
    via_stop: Optional[str] = None
    destination_stop: Optional[str] = None

    # Relationships
    trips: List[Trip] = Relationship(back_populates="pattern_jp")


"""
TRANSLATIONS
"""

class Translation(SQLModel, table=True):
    __tablename__ = "translations"
    
    table_name: str = Field(primary_key=True)
    field_name: str = Field(primary_key=True)
    language: str = Field(primary_key=True)
    translation: str
    record_id: Optional[str] = None
    record_sub_id: Optional[str] = None
    field_value: Optional[str] = None


"""
FEED INFO
"""

class FeedInfo(SQLModel, table=True):
    __tablename__ = "feed_info"
    
    feed_publisher_name: str = Field(primary_key=True)
    feed_publisher_url: str
    feed_lang: str = "ja"
    feed_start_date: Optional[str] = None
    feed_end_date: Optional[str] = None
    feed_version: Optional[str] = None

TABLE_MAP = {model.__tablename__: model for model in SQLModel.__subclasses__()}