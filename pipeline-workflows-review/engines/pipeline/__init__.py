"""
engines/pipeline/__init__.py
Folder Automations & Pipelines (FAP) Engine
Plugs into PIL/BIL as the routing nervous system.
"""
from .pipeline_engine import PipelineEngine
from .station_base import StationBase

from .external_adapter import ExternalStationAdapter
