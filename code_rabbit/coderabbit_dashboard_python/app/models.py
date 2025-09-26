from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class SeverityCount(BaseModel):
    severity: str
    count: int

class SuggestionTypeCount(BaseModel):
    type: str
    count: int

class DeveloperActivity(BaseModel):
    dev: str
    reviews: int
    comments: int
    avgResponseHrs: float

class TrendPoint(BaseModel):
    date: date
    issues: int
    prs: int
    mergeRate: float

class PR(BaseModel):
    id: int
    title: str
    author: str
    repo: str
    openedAt: date
    status: str
    issues: int
    critical: int

class Window(BaseModel):
    from_: date = Field(..., alias="from")
    to: date

class Totals(BaseModel):
    prsReviewed: int
    issues: int
    critical: int
    reviewers: int
    mergeRate: float
    medianResponseHrs: float

class DashboardPayload(BaseModel):
    window: Window
    totals: Totals
    issuesBySeverity: List[SeverityCount]
    suggestionsByType: List[SuggestionTypeCount]
    developerActivity: List[DeveloperActivity]
    trendDaily: List[TrendPoint]
    prs: List[PR]
