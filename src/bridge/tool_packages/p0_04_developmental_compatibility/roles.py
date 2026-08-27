from enum import StrEnum


class DevelopmentStageRole(StrEnum):
    EARLIER = "earlier"
    WITHIN_WINDOW = "within_window"
    LATER = "later"
    BRANCH_SHIFT = "branch_shift"
    UNRESOLVED = "unresolved"
