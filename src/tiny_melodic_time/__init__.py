# tiny-melodic-time
# Maps clock time to musical tempo and measure positions.
#
# Only public name re-exported here is TimeMapper. Keeping the surface area
# to a single class means downstream code cannot accidentally reach into
# helpers whose signatures may change between releases.

from .core import TimeMapper

__all__ = ["TimeMapper"]
