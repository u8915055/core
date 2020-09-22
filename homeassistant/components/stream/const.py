"""Constants for Stream component."""
DOMAIN = "stream"

CONF_STREAM_SOURCE = "stream_source"
CONF_LOOKBACK = "lookback"
CONF_DURATION = "duration"

ATTR_ENDPOINTS = "endpoints"
ATTR_STREAMS = "streams"
ATTR_KEEPALIVE = "keepalive"

SERVICE_RECORD = "record"

OUTPUT_FORMATS = ["hls"]

FORMAT_CONTENT_TYPE = {"hls": "application/vnd.apple.mpegurl"}

MAX_SEGMENTS = 3  # Max number of segments to keep around
MIN_SEGMENT_DURATION = 1.5  # Each segment is at least this many seconds

PACKETS_TO_WAIT_FOR_AUDIO = 20  # Some streams have an audio stream with no audio
