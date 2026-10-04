"""Quiet and sleep context based only on explicit or device-supported state."""
from dataclasses import dataclass
from enum import Enum
from backend.product.notifications import NotificationPriority
class QuietState(str,Enum):NORMAL="NORMAL";QUIET_HOURS="QUIET_HOURS";DO_NOT_DISTURB="DO_NOT_DISTURB";SLEEP_CONTEXT_UNKNOWN="SLEEP_CONTEXT_UNKNOWN";USER_MARKED_SLEEPING="USER_MARKED_SLEEPING"
@dataclass(frozen=True)
class QuietPresentationDecision:
 voice_allowed:bool;avatar_allowed:bool;queue_notification:bool;basis:QuietState

def quiet_decision(state:QuietState,priority:NotificationPriority)->QuietPresentationDecision:
 suppress=state in {QuietState.QUIET_HOURS,QuietState.DO_NOT_DISTURB,QuietState.USER_MARKED_SLEEPING} and priority!=NotificationPriority.CRITICAL
 return QuietPresentationDecision(not suppress,not suppress,suppress,state)
