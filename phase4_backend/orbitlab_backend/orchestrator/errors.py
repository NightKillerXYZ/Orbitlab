"""Typed errors for pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class PipelineError(Exception):
    stage: str
    code: str
    message: str
    details: Optional[Dict[str,Any]]=None
    def __str__(self):
        return f"[{self.stage}:{self.code}] {self.message}"

class NeedsClarification(PipelineError):
    def __init__(self, missing, details=None):
        super().__init__(stage="extract", code="needs_clarification", message=f"Missing required fields: {missing}", details={"missing":missing, **(details or {})})
        self.missing=missing

class ExtractionError(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="extract", code="extraction_error", message=msg, details=details)

class ExtractorUnavailable(PipelineError):
    def __init__(self, msg=None, details=None):
        message = msg or "The language model that reads your request is starting up or unreachable. Please try again in a minute."
        super().__init__(stage="extract", code="extractor_unavailable", message=message, details={"explanation": message, **(details or {})})

class InterpreterUnavailable(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="interpret", code="interpreter_unavailable", message=msg, details=details)

class InterpreterMismatch(PipelineError):
    def __init__(self, mismatches, details=None):
        msg=f"Interpreter returned mismatched values: {mismatches}"
        super().__init__(stage="verify", code="interpreter_mismatch", message=msg, details={"mismatches":mismatches, **(details or {})})
        self.mismatches=mismatches

class SchemaError(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="validate", code="schema_error", message=msg, details=details)

class ValidationFailed(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="validate", code="validation_failed", message=msg, details=details)

class CompileError(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="compile", code="compile_error", message=msg, details=details)

class GmatRunError(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="simulate", code="gmat_run_error", message=msg, details=details)

class GmatTimeout(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="simulate", code="gmat_timeout", message=msg, details=details)

class ParseError(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="parse", code="parse_error", message=msg, details=details)

class ExplainerError(PipelineError):
    def __init__(self, msg, details=None):
        super().__init__(stage="explain", code="explainer_error", message=msg, details=details)
