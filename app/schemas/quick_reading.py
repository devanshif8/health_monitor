from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class QuickReadingIn(BaseModel):
    """Combined reading entered by a doctor.

    All metric fields are optional, but at least one must be provided.
    """

    recorded_at: datetime
    heart_rate_bpm: float | None = Field(None, ge=20, le=250)
    systolic_bp_mmhg: float | None = Field(None, ge=50, le=250)
    diastolic_bp_mmhg: float | None = Field(None, ge=30, le=160)
    glucose_mg_dl: float | None = Field(None, ge=20, le=600)
    notes: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _at_least_one_metric(self):
        any_set = any(
            v is not None
            for v in (
                self.heart_rate_bpm,
                self.systolic_bp_mmhg,
                self.diastolic_bp_mmhg,
                self.glucose_mg_dl,
            )
        )
        if not any_set:
            raise ValueError("Provide at least one metric value")
        # Diastolic only makes sense paired with systolic
        if (self.diastolic_bp_mmhg is not None) != (self.systolic_bp_mmhg is not None):
            raise ValueError("Systolic and diastolic must both be provided together")
        return self


class QuickReadingOut(BaseModel):
    saved_metrics: list[str]
    recorded_at: datetime
