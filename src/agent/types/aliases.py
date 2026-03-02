from typing import Literal

GenerateType = Literal["mcq", "essay", "summary"]
JobKind = Literal["material", "lkpd"]
JobStatus = Literal[
    "accepted",
    "processing",
    "succeeded",
    "failed_processing",
    "failed_delivery",
]
CallbackStatus = Literal["succeeded", "failed_processing"]

