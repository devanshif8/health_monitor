from pydantic import BaseModel, Field, model_validator


class MetricRange(BaseModel):
    min: float = Field(..., ge=0)
    max: float = Field(..., gt=0)

    @model_validator(mode="after")
    def _min_lt_max(self):
        if self.min >= self.max:
            raise ValueError("min must be less than max")
        return self


class BloodPressureRange(MetricRange):
    min_secondary: float = Field(..., ge=0)
    max_secondary: float = Field(..., gt=0)

    @model_validator(mode="after")
    def _diastolic_min_lt_max(self):
        if self.min_secondary >= self.max_secondary:
            raise ValueError("min_secondary must be less than max_secondary")
        return self


class HealthyRangesIn(BaseModel):
    heart_rate: MetricRange
    blood_pressure: BloodPressureRange
    glucose: MetricRange


class HealthyRangesOut(HealthyRangesIn):
    pass
