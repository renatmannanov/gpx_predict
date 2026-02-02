"""
Base Pace Calculator

Abstract base class for all pace calculation methods.
Types are defined in shared/calculator_types.py to avoid circular imports.
"""

# Re-export everything from shared for backward compatibility
from app.shared.calculator_types import (
    SegmentType,
    MacroSegment,
    MethodResult,
    SegmentCalculation,
    CalculationResult,
    PaceCalculator,
)
